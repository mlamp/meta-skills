#!/usr/bin/env python3
"""Package and verify measured experiment raw records.

The archive is deterministic. The release commands require GitHub immutable
releases and keep publication separate from draft staging.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import re
import stat
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 2
SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
EXPERIMENT_RE = re.compile(r"E-[0-9]+")
LEGACY_ARTIFACTLESS_RUNS = {
    "r-20260817-4cccea322c": ("E-07", "f9d64f749a7fbb2604185f4d6d39085ae51c1b9e88dba80fb210c5a6fb95bc01"),
    "r-20260817-8fbcc01b2b": ("E-07", "0a3ca024718cf8f956bcf74f602962d16e2a15985e666d95381f63331e304bf5"),
    "r-20260817-d4d49120dc": ("E-08", "414664e7bac2606cc61c2f58ae61c492364f905bf375a0cb07deada9a2b52ae7"),
    "r-20260817-48eac1a620": ("E-08", "f12a8ebe27303dec0bac0b1edce133943fe9c7f98ea8e12f524868821211e4a0"),
}


class ArtifactError(RuntimeError):
    pass


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path, label: str):
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ArtifactError(f"{label} is absent: {path}") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ArtifactError(f"{label} is not an unlinked regular file: {path}")


def load_json(path: Path):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"cannot read JSON: {path}") from exc


def fsync_directory(path: Path):
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def install_temporary(temporary: Path, target: Path, allow_identical=False):
    try:
        os.link(temporary, target)
        fsync_directory(target.parent)
    except FileExistsError as exc:
        if allow_identical and target.is_file() and not target.is_symlink():
            if target.stat().st_size == temporary.stat().st_size and sha256_file(target) == sha256_file(temporary):
                return
        raise ArtifactError(f"refusing to overwrite: {target}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def write_bytes_atomic(path: Path, data: bytes, allow_identical=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            os.fchmod(handle.fileno(), 0o644)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        install_temporary(temporary, path, allow_identical=allow_identical)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def write_json_exclusive(path: Path, value):
    data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    write_bytes_atomic(path, data)


def write_json_idempotent(path: Path, value):
    data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    write_bytes_atomic(path, data, allow_identical=True)


def copy_exclusive(source: Path, target: Path):
    require_regular_file(source, "source manifest")
    data = source.read_bytes()
    if target.exists():
        require_regular_file(target, "committed manifest")
        if target.read_bytes() != data:
            raise ArtifactError(f"committed manifest differs: {target}")
        return
    write_bytes_atomic(target, data, allow_identical=True)


def read_dotenv(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in ("'", '"'):
            value = value[1:-1]
        values[name] = value
    return values


def safe_relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ArtifactError("artifact member path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(part in ("", ".", "..") for part in path.parts):
        raise ArtifactError(f"unsafe artifact member path: {value!r}")
    return path


def safe_asset_name(value: str) -> str:
    path = safe_relative(value)
    if len(path.parts) != 1 or value.startswith("-"):
        raise ArtifactError(f"unsafe release asset name: {value!r}")
    return value


def require_sha256(value, field: str):
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ArtifactError(f"{field} must be a lowercase SHA-256")


def require_commit(value, field: str):
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise ArtifactError(f"{field} must be a full lowercase commit SHA")


def validate_repository(repository):
    if not isinstance(repository, dict):
        raise ArtifactError("repository must be an object")
    if not isinstance(repository.get("id"), int) or repository["id"] <= 0:
        raise ArtifactError("repository requires a positive immutable numeric id")
    if not isinstance(repository.get("name"), str) or REPOSITORY_RE.fullmatch(repository["name"]) is None:
        raise ArtifactError("repository name must be owner/name")
    if any(part in (".", "..") for part in repository["name"].split("/")):
        raise ArtifactError("repository name contains an unsafe path segment")


def validate_release(release):
    if not isinstance(release, dict):
        raise ArtifactError("release must be an object")
    tag = release.get("tag")
    if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
        raise ArtifactError("release tag contains unsafe characters")
    for field in ("archive_asset_name", "manifest_asset_name"):
        safe_asset_name(release.get(field))
    if release["archive_asset_name"] == release["manifest_asset_name"]:
        raise ArtifactError("release asset names must differ")


def validate_hash_map(value, field: str):
    if not isinstance(value, dict) or not value:
        raise ArtifactError(f"{field} must be a non-empty hash map")
    for name, digest in value.items():
        safe_relative(name)
        require_sha256(digest, f"{field}.{name}")


def validate_schedule(value):
    if not isinstance(value, dict) or not value:
        raise ArtifactError("schedule must be a non-empty hash map")
    for name, digest in value.items():
        if not isinstance(name, str) or not name.endswith("_sha256"):
            raise ArtifactError("schedule keys must end in _sha256")
        require_sha256(digest, f"schedule.{name}")


def validate_execution(execution, exclusions):
    if not isinstance(exclusions, list):
        raise ArtifactError("exclusions must be a list")
    for row in exclusions:
        if not isinstance(row, dict):
            raise ArtifactError("each exclusion must be an object")
        safe_relative(row.get("path"))
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ArtifactError("each exclusion requires a non-empty reason")
    if not isinstance(execution, dict):
        raise ArtifactError("execution must be an object")
    required = {"call_manifest", "record_status_counts", "retry_attempts", "exclusion_count"}
    if set(execution) != required:
        raise ArtifactError(f"execution requires exactly {sorted(required)}")
    calls = execution["call_manifest"]
    if not isinstance(calls, dict) or set(calls) != {"started", "completed"}:
        raise ArtifactError("execution.call_manifest requires started and completed")
    counts = execution["record_status_counts"]
    if not isinstance(counts, dict) or not counts:
        raise ArtifactError("execution.record_status_counts must be non-empty")
    numeric = [*calls.values(), *counts.values(), execution["retry_attempts"], execution["exclusion_count"]]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in numeric):
        raise ArtifactError("execution counts must be non-negative integers")
    if execution["exclusion_count"] != len(exclusions):
        raise ArtifactError("execution exclusion_count differs from exclusions")


def kind_counts(rows) -> dict[str, int]:
    result = {}
    for row in rows:
        kind = row.get("kind") if isinstance(row, dict) else None
        if not isinstance(kind, str) or not kind:
            raise ArtifactError("inventory member requires a non-empty kind")
        result[kind] = result.get(kind, 0) + 1
    return result


def validate_raw_root(plan, raw_root: Path, repo_root: Path) -> Path:
    declared = safe_relative(plan.get("raw_root")).as_posix()
    if raw_root.is_symlink():
        raise ArtifactError(f"symlink is forbidden: {raw_root}")
    try:
        repository = repo_root.resolve(strict=True)
        resolved = raw_root.resolve(strict=True)
        actual = resolved.relative_to(repository).as_posix()
    except (OSError, ValueError) as exc:
        raise ArtifactError("raw root must exist beneath repo_root") from exc
    if actual != declared:
        raise ArtifactError(f"raw root differs from plan; declared={declared}, actual={actual}")
    return resolved


def expected_map(plan) -> dict[str, str]:
    rows = plan.get("expected_members")
    if not isinstance(rows, list) or not rows:
        raise ArtifactError("plan requires a non-empty expected_members list")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("kind"), str) or not row["kind"]:
            raise ArtifactError("each expected member requires path and kind")
        path = safe_relative(row.get("path"))
        if path.as_posix() in result:
            raise ArtifactError(f"duplicate expected member: {path}")
        result[path.as_posix()] = row["kind"]
    return result


def actual_regular_files(raw_root: Path) -> dict[str, Path]:
    if raw_root.is_symlink():
        raise ArtifactError(f"symlink is forbidden: {raw_root}")
    if not raw_root.is_dir():
        raise ArtifactError(f"raw root is not a directory: {raw_root}")
    result = {}
    def walk_error(error):
        raise ArtifactError(f"cannot traverse raw root: {error.filename or raw_root}") from error

    for directory, dirnames, filenames in os.walk(raw_root, followlinks=False, onerror=walk_error):
        base = Path(directory)
        for name in list(dirnames):
            child = base / name
            if child.is_symlink():
                raise ArtifactError(f"symlink is forbidden: {child}")
        for name in filenames:
            child = base / name
            relative = child.relative_to(raw_root).as_posix()
            safe_relative(relative)
            stat = child.lstat()
            if child.is_symlink():
                raise ArtifactError(f"symlink is forbidden: {child}")
            if not child.is_file():
                raise ArtifactError(f"only regular files are allowed: {child}")
            if stat.st_nlink != 1:
                raise ArtifactError(f"hard-linked file is forbidden: {child}")
            result[relative] = child
    return result


def configured_secret_values(plan, repo_root: Path) -> list[str]:
    dotenv = read_dotenv(repo_root / ".env")
    names = set(plan.get("credential_env_names", []))
    names.update(name for name in dotenv if name.endswith(SECRET_SUFFIXES))
    names.update(name for name in os.environ if name.endswith(SECRET_SUFFIXES))
    values = set()
    for name in names:
        for value in (os.environ.get(name), dotenv.get(name)):
            if value:
                values.add(value)
    return sorted(values)


def read_regular_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ArtifactError(f"cannot open regular raw member: {path}") from exc
    with os.fdopen(descriptor, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ArtifactError(f"raw member changed or is linked: {path}")
        return handle.read()


def json_strings(value, remaining_decodes=4, seen=None):
    seen = seen or set()
    if isinstance(value, str):
        yield value
        candidate = value.strip()
        if remaining_decodes and candidate[:1] in ("{", "[", '"') and candidate not in seen:
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                return
            yield from json_strings(decoded, remaining_decodes - 1, seen | {candidate})
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from json_strings(key, remaining_decodes, seen)
            yield from json_strings(item, remaining_decodes, seen)
    elif isinstance(value, list):
        for item in value:
            yield from json_strings(item, remaining_decodes, seen)


def scan_members(plan, files: dict[str, Path], repo_root: Path):
    secret_values = configured_secret_values(plan, repo_root)
    patterns = []
    for row in plan.get("forbidden_patterns", []):
        try:
            patterns.append((row["id"], re.compile(row["regex"])))
        except (KeyError, TypeError, re.error) as exc:
            raise ArtifactError("invalid forbidden_patterns entry") from exc
    scanned_bytes = 0
    contents = {}
    for relative, path in sorted(files.items()):
        data = read_regular_bytes(path)
        contents[relative] = data
        scanned_bytes += len(data)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactError(f"raw member is not UTF-8 text: {relative}") from exc
        try:
            if relative.endswith(".json"):
                documents = [json.loads(text)]
            elif relative.endswith(".jsonl"):
                documents = []
                for number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        documents.append(json.loads(line))
            else:
                raise ArtifactError(f"raw member must be JSON or JSONL: {relative}")
        except json.JSONDecodeError as exc:
            raise ArtifactError(f"raw member has invalid JSON: {relative}:{exc.lineno}") from exc
        decoded_strings = list(json_strings(documents))
        for secret in secret_values:
            if secret.encode() in data or any(secret in value for value in decoded_strings):
                raise ArtifactError(f"configured credential found in {relative}")
        scan_texts = [text, *decoded_strings]
        for pattern_id, pattern in patterns:
            if any(pattern.search(value) for value in scan_texts):
                raise ArtifactError(f"sanitization pattern {pattern_id} matched {relative}")
    report = {
        "exact_secret_scan": "configured names plus credential-suffixed environment and .env values",
        "files_scanned": len(files),
        "forbidden_pattern_ids": [row[0] for row in patterns],
        "scanned_bytes": scanned_bytes,
        "status": "passed",
    }
    return {**report, "report_sha256": sha256_bytes(canonical(report).encode())}, contents


def create_archive(contents: dict[str, bytes], members: list[str], archive_path: Path):
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.", suffix=".tmp", dir=archive_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as raw_handle:
            descriptor = -1
            os.fchmod(raw_handle.fileno(), 0o644)
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, compresslevel=9, mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    for relative in members:
                        data = contents[relative]
                        info = tarfile.TarInfo(relative)
                        info.size = len(data)
                        info.mtime = 0
                        info.mode = 0o644
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.pax_headers = {}
                        archive.addfile(info, io.BytesIO(data))
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        install_temporary(temporary, archive_path, allow_identical=True)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ArtifactError("plan must be an object")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError(f"plan schema_version must be {SCHEMA_VERSION}")
    for field in (
        "repository", "experiment", "batch_id", "raw_root", "frozen_commit",
        "freeze_sha256", "packager_commit", "provenance", "schedule", "release",
        "expected_counts", "credential_env_names", "forbidden_patterns", "execution",
    ):
        if not plan.get(field):
            raise ArtifactError(f"plan requires {field}")
    for field in ("experiment", "batch_id"):
        if not isinstance(plan[field], str) or not plan[field]:
            raise ArtifactError(f"plan requires a non-empty string {field}")
    if TAG_RE.fullmatch(plan["batch_id"]) is None:
        raise ArtifactError("batch_id contains unsafe characters")
    safe_relative(plan["raw_root"])
    validate_repository(plan["repository"])
    validate_release(plan["release"])
    require_commit(plan["frozen_commit"], "frozen_commit")
    require_commit(plan["packager_commit"], "packager_commit")
    if plan["packager_commit"] != plan["frozen_commit"]:
        raise ArtifactError("packager_commit must equal frozen_commit")
    require_sha256(plan["freeze_sha256"], "freeze_sha256")
    validate_hash_map(plan["provenance"], "provenance")
    validate_schedule(plan["schedule"])
    expected = expected_map(plan)
    if not isinstance(plan["expected_counts"], dict) or plan["expected_counts"] != kind_counts([
        {"kind": kind} for kind in expected.values()
    ]):
        raise ArtifactError("expected_counts differ from expected_members")
    names = plan["credential_env_names"]
    if not isinstance(names, list) or not names or any(
        not isinstance(name, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None for name in names
    ):
        raise ArtifactError("credential_env_names must be a non-empty list of environment names")
    patterns = plan["forbidden_patterns"]
    if not isinstance(patterns, list) or not patterns:
        raise ArtifactError("forbidden_patterns must be a non-empty list")
    pattern_ids = []
    for row in patterns:
        try:
            pattern_ids.append(row["id"])
            re.compile(row["regex"])
        except (KeyError, TypeError, re.error) as exc:
            raise ArtifactError("invalid forbidden_patterns entry") from exc
    if len(pattern_ids) != len(set(pattern_ids)) or any(not isinstance(value, str) or not value for value in pattern_ids):
        raise ArtifactError("forbidden pattern ids must be unique non-empty strings")
    if "exclusions" not in plan or "supersedes" not in plan:
        raise ArtifactError("plan requires exclusions and supersedes fields")
    validate_execution(plan["execution"], plan["exclusions"])
    supersedes = plan["supersedes"]
    if supersedes is not None and (not isinstance(supersedes, str) or TAG_RE.fullmatch(supersedes) is None):
        raise ArtifactError("supersedes must be null or a safe release tag")


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError("unsupported manifest schema")
    for field in (
        "repository", "experiment", "batch_id", "raw_root", "frozen_commit", "freeze_sha256",
        "packager_commit", "provenance", "schedule", "release", "exclusions", "execution",
        "inventory", "sanitization", "archive",
    ):
        if field not in manifest:
            raise ArtifactError(f"manifest requires {field}")
    validate_repository(manifest["repository"])
    validate_release(manifest["release"])
    for field in ("experiment", "batch_id"):
        if not isinstance(manifest[field], str) or not manifest[field]:
            raise ArtifactError(f"manifest requires a non-empty string {field}")
    if TAG_RE.fullmatch(manifest["batch_id"]) is None:
        raise ArtifactError("batch_id contains unsafe characters")
    safe_relative(manifest["raw_root"])
    require_commit(manifest["frozen_commit"], "frozen_commit")
    require_commit(manifest["packager_commit"], "packager_commit")
    if manifest["packager_commit"] != manifest["frozen_commit"]:
        raise ArtifactError("packager_commit must equal frozen_commit")
    require_sha256(manifest["freeze_sha256"], "freeze_sha256")
    validate_hash_map(manifest["provenance"], "provenance")
    validate_schedule(manifest["schedule"])
    validate_execution(manifest["execution"], manifest["exclusions"])
    supersedes = manifest.get("supersedes")
    if supersedes is not None and (not isinstance(supersedes, str) or TAG_RE.fullmatch(supersedes) is None):
        raise ArtifactError("supersedes must be null or a safe release tag")
    inventory = manifest["inventory"]
    if not isinstance(inventory, dict) or set(inventory) != {"expected_counts", "actual_counts", "members"}:
        raise ArtifactError("manifest inventory has the wrong fields")
    members = inventory["members"]
    if not isinstance(members, list) or not members:
        raise ArtifactError("manifest member inventory is empty")
    paths = []
    for row in members:
        if not isinstance(row, dict) or set(row) != {"bytes", "kind", "path", "sha256"}:
            raise ArtifactError("manifest member has the wrong fields")
        paths.append(safe_relative(row["path"]).as_posix())
        if not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool) or row["bytes"] < 0:
            raise ArtifactError("manifest member bytes must be a non-negative integer")
        require_sha256(row["sha256"], f"inventory.{row['path']}")
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ArtifactError("manifest member inventory must be unique and sorted")
    counts = kind_counts(members)
    if inventory["expected_counts"] != counts or inventory["actual_counts"] != counts:
        raise ArtifactError("manifest inventory counts differ from member rows")
    sanitization = manifest["sanitization"]
    required_scan = {
        "exact_secret_scan", "files_scanned", "forbidden_pattern_ids", "scanned_bytes", "status", "report_sha256"
    }
    if not isinstance(sanitization, dict) or set(sanitization) != required_scan or sanitization.get("status") != "passed":
        raise ArtifactError("manifest sanitization report is invalid")
    report = {key: value for key, value in sanitization.items() if key != "report_sha256"}
    require_sha256(sanitization["report_sha256"], "sanitization.report_sha256")
    if sanitization["report_sha256"] != sha256_bytes(canonical(report).encode()):
        raise ArtifactError("sanitization report digest is invalid")
    if sanitization.get("files_scanned") != len(members):
        raise ArtifactError("sanitization file count differs from inventory")
    archive = manifest["archive"]
    if not isinstance(archive, dict) or set(archive) != {"asset_name", "bytes", "format", "sha256"}:
        raise ArtifactError("manifest archive metadata is invalid")
    if archive["asset_name"] != manifest["release"]["archive_asset_name"]:
        raise ArtifactError("archive asset name differs from release")
    if not isinstance(archive["bytes"], int) or isinstance(archive["bytes"], bool) or archive["bytes"] < 0:
        raise ArtifactError("archive bytes must be a non-negative integer")
    require_sha256(archive["sha256"], "archive.sha256")
    expected_format = "tar.gz:pax; gzip=9; mtime=0; uid=gid=0; mode=0644; sorted=true"
    if archive["format"] != expected_format:
        raise ArtifactError("archive format contract differs")
    return manifest


def pack(plan, raw_root: Path, archive_path: Path, manifest_path: Path, repo_root: Path):
    validate_plan(plan)
    raw_root = validate_raw_root(plan, raw_root, repo_root)
    expected = expected_map(plan)
    actual = actual_regular_files(raw_root)
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing or unexpected:
        raise ArtifactError(f"inventory mismatch; missing={missing}, unexpected={unexpected}")
    scan, contents = scan_members(plan, actual, repo_root)
    members = sorted(expected)
    member_rows = [{
        "bytes": len(contents[path]),
        "kind": expected[path],
        "path": path,
        "sha256": sha256_bytes(contents[path]),
    } for path in members]
    actual_counts = {}
    for row in member_rows:
        actual_counts[row["kind"]] = actual_counts.get(row["kind"], 0) + 1
    expected_counts = plan["expected_counts"]
    if actual_counts != expected_counts:
        raise ArtifactError(f"kind counts differ; expected={expected_counts}, actual={actual_counts}")
    create_archive(contents, members, archive_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "repository": plan["repository"],
        "experiment": plan["experiment"],
        "batch_id": plan["batch_id"],
        "raw_root": plan["raw_root"],
        "frozen_commit": plan["frozen_commit"],
        "freeze_sha256": plan["freeze_sha256"],
        "packager_commit": plan["packager_commit"],
        "provenance": plan["provenance"],
        "schedule": plan["schedule"],
        "release": plan["release"],
        "supersedes": plan["supersedes"],
        "exclusions": plan["exclusions"],
        "execution": plan["execution"],
        "inventory": {
            "expected_counts": expected_counts,
            "actual_counts": actual_counts,
            "members": member_rows,
        },
        "sanitization": scan,
        "archive": {
            "asset_name": plan["release"]["archive_asset_name"],
            "bytes": archive_path.stat().st_size,
            "format": "tar.gz:pax; gzip=9; mtime=0; uid=gid=0; mode=0644; sorted=true",
            "sha256": sha256_file(archive_path),
        },
    }
    write_json_idempotent(manifest_path, manifest)
    verify_local(manifest_path, archive_path)
    return manifest


def verify_local(manifest_path: Path, archive_path: Path):
    require_regular_file(manifest_path, "manifest")
    require_regular_file(archive_path, "archive")
    manifest = validate_manifest(load_json(manifest_path))
    archive_meta = manifest.get("archive", {})
    if archive_meta.get("sha256") != sha256_file(archive_path):
        raise ArtifactError("archive SHA-256 differs from manifest")
    if archive_meta.get("bytes") != archive_path.stat().st_size:
        raise ArtifactError("archive size differs from manifest")
    expected = {row["path"]: row for row in manifest["inventory"]["members"]}
    for path in expected:
        safe_relative(path)
    seen = {}
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for info in archive:
                safe_relative(info.name)
                if info.name in seen:
                    raise ArtifactError(f"duplicate archive member: {info.name}")
                if not info.isreg() or info.issym() or info.islnk():
                    raise ArtifactError(f"archive member is not regular: {info.name}")
                if (info.uid, info.gid, info.mode, info.mtime, info.uname, info.gname) != (0, 0, 0o644, 0, "", ""):
                    raise ArtifactError(f"archive metadata is not normalized: {info.name}")
                handle = archive.extractfile(info)
                if handle is None:
                    raise ArtifactError(f"cannot read archive member: {info.name}")
                data = handle.read()
                seen[info.name] = {"bytes": len(data), "sha256": sha256_bytes(data)}
    except (tarfile.TarError, OSError) as exc:
        raise ArtifactError("cannot read archive") from exc
    if set(seen) != set(expected):
        raise ArtifactError("archive members differ from manifest")
    for path, values in seen.items():
        if values["bytes"] != expected[path].get("bytes") or values["sha256"] != expected[path].get("sha256"):
            raise ArtifactError(f"archive member differs from manifest: {path}")
    return manifest


def verify_source(manifest_path: Path, plan, raw_root: Path, repo_root: Path):
    validate_plan(plan)
    raw_root = validate_raw_root(plan, raw_root, repo_root)
    manifest = validate_manifest(load_json(manifest_path))
    expected_fields = (
        "repository", "experiment", "batch_id", "raw_root", "frozen_commit", "freeze_sha256",
        "packager_commit", "provenance", "schedule", "release", "supersedes", "exclusions", "execution",
    )
    for field in expected_fields:
        if manifest.get(field) != plan.get(field):
            raise ArtifactError(f"existing manifest differs from current plan: {field}")
    expected = expected_map(plan)
    actual = actual_regular_files(raw_root)
    if set(actual) != set(expected):
        raise ArtifactError("current raw inventory differs from existing manifest")
    scan, contents = scan_members(plan, actual, repo_root)
    if manifest.get("sanitization") != scan:
        raise ArtifactError("current sanitization result differs from existing manifest")
    rows = {row["path"]: row for row in manifest.get("inventory", {}).get("members", [])}
    if set(rows) != set(expected):
        raise ArtifactError("existing manifest inventory differs from current plan")
    for path, kind in expected.items():
        if rows[path].get("kind") != kind:
            raise ArtifactError(f"existing manifest kind differs: {path}")
        if rows[path].get("bytes") != len(contents[path]) or rows[path].get("sha256") != sha256_bytes(contents[path]):
            raise ArtifactError(f"current raw member differs from existing manifest: {path}")
    counts = kind_counts(list(rows.values()))
    if counts != plan["expected_counts"]:
        raise ArtifactError("existing manifest counts differ from current plan")
    return manifest


def run(command: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    try:
        process = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ArtifactError(f"command timed out: {' '.join(command[:3])}") from exc
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ArtifactError(f"command failed: {' '.join(command[:3])}: {detail}")
    return process.stdout.strip()


def gh_json(repo: str, endpoint: str):
    resource = f"repos/{repo}" + (f"/{endpoint}" if endpoint else "")
    output = run(["gh", "api", resource])
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"GitHub returned invalid JSON for {endpoint}") from exc


def gh_paginated_json(repo: str, endpoint: str):
    resource = f"repos/{repo}/{endpoint}"
    output = run(["gh", "api", "--paginate", "--slurp", resource])
    try:
        pages = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"GitHub returned invalid paginated JSON for {endpoint}") from exc
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ArtifactError(f"GitHub returned the wrong paginated shape for {endpoint}")
    return [row for page in pages for row in page]


def require_immutable_releases(repo: str):
    setting = gh_json(repo, "immutable-releases")
    if setting.get("enabled") is not True:
        raise ArtifactError("repository immutable releases are not enabled")


def verify_repository_identity(manifest):
    expected = manifest["repository"]
    actual = gh_json(expected["name"], "")
    if actual.get("id") != expected["id"] or actual.get("full_name") != expected["name"]:
        raise ArtifactError("GitHub repository identity differs from manifest")
    return actual


def server_asset_map(release):
    assets = release.get("assets", [])
    result = {asset["name"]: asset for asset in assets}
    if len(result) != len(assets):
        raise ArtifactError("release has duplicate asset names")
    return result


def expected_server_digest(local_path: Path) -> str:
    return "sha256:" + sha256_file(local_path)


def release_by_tag_any_state(repo: str, tag: str, required=True):
    matches = [release for release in gh_paginated_json(repo, "releases?per_page=100")
               if release.get("tag_name") == tag]
    if len(matches) > 1:
        raise ArtifactError(f"multiple releases use tag: {tag}")
    if matches:
        return matches[0]
    if required:
        raise ArtifactError(f"release does not exist: {tag}")
    return None


def verify_server_assets(release, manifest_path: Path, archive_path: Path):
    manifest = load_json(manifest_path)
    assets = server_asset_map(release)
    expected = {
        manifest["release"]["archive_asset_name"]: archive_path,
        manifest["release"]["manifest_asset_name"]: manifest_path,
    }
    if set(assets) != set(expected):
        raise ArtifactError(f"release assets differ; expected={sorted(expected)}, actual={sorted(assets)}")
    for name, path in expected.items():
        asset = assets[name]
        if asset.get("size") != path.stat().st_size:
            raise ArtifactError(f"server size differs for {name}")
        if asset.get("digest") != expected_server_digest(path):
            raise ArtifactError(f"server digest differs for {name}")


def wait_for_server_assets(repo: str, release_id: int, manifest_path: Path, archive_path: Path):
    last_error = None
    for _ in range(15):
        release = gh_json(repo, f"releases/{release_id}")
        try:
            verify_server_assets(release, manifest_path, archive_path)
            return release
        except ArtifactError as exc:
            last_error = exc
            time.sleep(2)
    raise last_error or ArtifactError("release assets did not become verifiable")


def commit_is_on_default_branch(repo: str, commit: str, repository=None):
    repository = repository or gh_json(repo, "")
    default = repository["default_branch"]
    comparison = gh_json(repo, f"compare/{commit}...{default}")
    if comparison.get("status") not in ("ahead", "identical"):
        raise ArtifactError(f"frozen commit is not contained in {default}")


def require_local_frozen_head(repo_root: Path, frozen_commit: str):
    root = repo_root.resolve(strict=True)
    head = run(["git", "-C", str(root), "rev-parse", "HEAD"])
    if head != frozen_commit:
        raise ArtifactError("local HEAD must equal frozen_commit")


def verify_superseded_release(manifest):
    old_tag = manifest.get("supersedes")
    if not old_tag:
        return
    if not isinstance(old_tag, str) or old_tag == manifest["release"]["tag"]:
        raise ArtifactError("supersedes must name a different release tag")
    old_release = gh_json(manifest["repository"]["name"], f"releases/tags/{old_tag}")
    if old_release.get("draft") or old_release.get("immutable") is not True:
        raise ArtifactError("supersedes must name a published immutable release")


def stage_release(manifest_path: Path, archive_path: Path, plan, raw_root: Path, repo_root: Path):
    manifest = verify_local(manifest_path, archive_path)
    verify_source(manifest_path, plan, raw_root, repo_root)
    require_local_frozen_head(repo_root, manifest["frozen_commit"])
    repo = manifest["repository"]["name"]
    require_immutable_releases(repo)
    repository = verify_repository_identity(manifest)
    commit_is_on_default_branch(repo, manifest["frozen_commit"], repository)
    verify_superseded_release(manifest)
    if manifest["packager_commit"] != manifest["frozen_commit"]:
        raise ArtifactError("packager_commit must equal frozen_commit")
    tag = manifest["release"]["tag"]
    release = release_by_tag_any_state(repo, tag, required=False)
    if release is not None:
        if release.get("draft") is not True or release.get("target_commitish") != manifest["frozen_commit"]:
            raise ArtifactError(f"existing release is not the exact resumable draft: {tag}")
        run([
            "gh", "release", "upload", tag, "-R", repo, "--clobber",
            str(archive_path), str(manifest_path),
        ], timeout=600)
    else:
        run([
            "gh", "release", "create", tag, "-R", repo, "--draft",
            "--target", manifest["frozen_commit"], "--title", tag,
            "--notes", f"Raw evidence for {manifest['experiment']} batch {manifest['batch_id']}.",
            str(archive_path), str(manifest_path),
        ], timeout=600)
        release = release_by_tag_any_state(repo, tag)
    release = wait_for_server_assets(repo, release["id"], manifest_path, archive_path)
    if release.get("draft") is not True:
        raise ArtifactError("staged release is not a draft")
    return {"release_id": release["id"], "state": "draft", "tag": tag}


def resolve_tag_commit(repo: str, tag: str) -> str:
    ref = gh_json(repo, f"git/ref/tags/{tag}")
    target = ref["object"]
    for _ in range(3):
        if target.get("type") == "commit":
            return target["sha"]
        if target.get("type") != "tag":
            break
        target = gh_json(repo, f"git/tags/{target['sha']}")["object"]
    raise ArtifactError(f"tag does not resolve to a commit: {tag}")


def download_and_verify(
    manifest: dict, committed_manifest: Path | None = None, expected_repository: str | None = None
):
    validate_manifest(manifest)
    repo = manifest["repository"]["name"]
    if expected_repository is not None and repo != expected_repository:
        raise ArtifactError(
            f"manifest repository differs from verifier repository; expected={expected_repository}, actual={repo}"
        )
    tag = manifest["release"]["tag"]
    verify_repository_identity(manifest)
    release = gh_json(repo, f"releases/tags/{tag}")
    if release.get("draft") or release.get("immutable") is not True:
        raise ArtifactError("release is not published and immutable")
    if resolve_tag_commit(repo, tag) != manifest["frozen_commit"]:
        raise ArtifactError("release tag points to the wrong commit")
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary)
        run(["gh", "release", "download", tag, "-R", repo, "--dir", str(target)], timeout=600)
        archive = target / manifest["release"]["archive_asset_name"]
        released_manifest = target / manifest["release"]["manifest_asset_name"]
        source_manifest = committed_manifest or released_manifest
        require_regular_file(archive, "downloaded archive")
        require_regular_file(released_manifest, "downloaded manifest")
        require_regular_file(source_manifest, "source manifest")
        if released_manifest.read_bytes() != source_manifest.read_bytes():
            raise ArtifactError("released manifest differs from committed manifest")
        verify_server_assets(release, released_manifest, archive)
        verify_local(released_manifest, archive)
        run(["gh", "release", "verify", tag, "-R", repo, "--format", "json"])
        run(["gh", "release", "verify-asset", tag, str(archive), "-R", repo, "--format", "json"])
    return {
        "archive_sha256": manifest["archive"]["sha256"],
        "attestations": {
            "archive": {
                "asset_name": manifest["release"]["archive_asset_name"],
                "sha256": manifest["archive"]["sha256"],
            },
            "release": {
                "release_id": release["id"],
                "repository_id": manifest["repository"]["id"],
                "tag": tag,
            },
        },
        "manifest_sha256": sha256_file(source_manifest),
        "release_id": release["id"],
        "release_tag": tag,
        "verified": True,
    }


def publish_release(
    manifest_path: Path, archive_path: Path, confirm_tag: str, committed_copy: Path,
    plan, raw_root: Path, repo_root: Path,
):
    manifest = verify_local(manifest_path, archive_path)
    verify_source(manifest_path, plan, raw_root, repo_root)
    require_local_frozen_head(repo_root, manifest["frozen_commit"])
    repo = manifest["repository"]["name"]
    tag = manifest["release"]["tag"]
    if confirm_tag != tag:
        raise ArtifactError("--confirm-tag must exactly match the manifest tag")
    require_immutable_releases(repo)
    repository = verify_repository_identity(manifest)
    commit_is_on_default_branch(repo, manifest["frozen_commit"], repository)
    verify_superseded_release(manifest)
    if manifest["packager_commit"] != manifest["frozen_commit"]:
        raise ArtifactError("packager_commit must equal frozen_commit")
    release = release_by_tag_any_state(repo, tag)
    if release.get("draft") is True:
        if release.get("target_commitish") != manifest["frozen_commit"]:
            raise ArtifactError("draft release targets the wrong commit")
        verify_server_assets(release, manifest_path, archive_path)
        run(["gh", "release", "edit", tag, "-R", repo, "--draft=false", "--latest=false"])
    for _ in range(15):
        release = gh_json(repo, f"releases/{release['id']}")
        if release.get("immutable") is True:
            break
        time.sleep(2)
    else:
        raise ArtifactError("published release did not become immutable")
    receipt = download_and_verify(manifest, manifest_path)
    copy_exclusive(manifest_path, committed_copy)
    return receipt


def repo_file(repo_root: Path, relative: str) -> Path:
    path = safe_relative(relative)
    try:
        root = repo_root.resolve(strict=True)
        unresolved = root
        for part in path.parts:
            unresolved = unresolved / part
            if unresolved.is_symlink():
                raise ArtifactError(f"tracked path contains a symlink: {relative}")
        target = unresolved.resolve(strict=True)
        target.relative_to(root)
    except ArtifactError:
        raise
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"tracked path is absent or outside the repository: {relative}") from exc
    require_regular_file(target, "tracked path")
    return target


def load_jsonl(path: Path):
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ArtifactError(f"cannot read JSONL: {path}") from exc
    rows = []
    for number, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArtifactError(f"invalid JSONL: {path}:{number}") from exc
        if not isinstance(row, dict):
            raise ArtifactError(f"JSONL row is not an object: {path}:{number}")
        rows.append(row)
    return rows


def experiment_directory(experiment: str) -> str:
    if EXPERIMENT_RE.fullmatch(experiment) is None:
        raise ArtifactError(f"artifact-backed experiment id is invalid: {experiment}")
    return experiment.lower().replace("-", "")


def verify_ledger_references(
    repo_root: Path, expected_repository: str | None = None, verify_remote=False,
    baseline_ledger: Path | None = None,
):
    if verify_remote and expected_repository is None:
        raise ArtifactError("remote ledger verification requires expected_repository")
    ledger = repo_file(repo_root, "ledger/runs.jsonl")
    if baseline_ledger is not None:
        require_regular_file(baseline_ledger, "baseline ledger")
        baseline = baseline_ledger.read_bytes()
        current = ledger.read_bytes()
        if not current.startswith(baseline):
            raise ArtifactError("ledger is not an append-only extension of the baseline")
    ledger_rows = load_jsonl(ledger)
    run_ids = [row.get("run_id") for row in ledger_rows]
    if any(not isinstance(run_id, str) or not run_id for run_id in run_ids) or len(run_ids) != len(set(run_ids)):
        raise ArtifactError("ledger run_ids must be non-empty and unique")
    checked = 0
    legacy_seen = set()
    remote_receipts = {}
    for row in ledger_rows:
        legacy = LEGACY_ARTIFACTLESS_RUNS.get(row.get("run_id"))
        if legacy is not None:
            expected_experiment, expected_sha256 = legacy
            if row.get("experiment") != expected_experiment \
                    or sha256_bytes(canonical(row).encode()) != expected_sha256:
                raise ArtifactError(f"legacy artifactless row differs from its pin: {row.get('run_id')}")
            legacy_seen.add(row["run_id"])
        if "artifact" not in row:
            if EXPERIMENT_RE.fullmatch(str(row.get("experiment", ""))) is not None:
                if legacy is None:
                    raise ArtifactError(f"measured experiment row requires artifact evidence: {row.get('run_id')}")
            continue
        if row.get("type") != "experiment" or EXPERIMENT_RE.fullmatch(str(row.get("experiment", ""))) is None:
            raise ArtifactError("only exact numeric experiment rows may carry artifact references")
        if row.get("schema_version") != 2:
            raise ArtifactError(f"artifact-backed ledger row requires schema_version 2: {row.get('run_id')}")
        artifact = row["artifact"]
        required = {
            "archive_sha256", "attestations", "manifest_path", "manifest_sha256",
            "release_id", "release_tag", "verified",
        }
        if not isinstance(artifact, dict) or set(artifact) != required or artifact.get("verified") is not True:
            raise ArtifactError(f"ledger artifact receipt is invalid: {row.get('run_id')}")
        if not isinstance(artifact["release_id"], int) or isinstance(artifact["release_id"], bool) \
                or artifact["release_id"] <= 0:
            raise ArtifactError(f"ledger release_id is invalid: {row.get('run_id')}")
        require_sha256(artifact["archive_sha256"], "ledger artifact.archive_sha256")
        require_sha256(artifact["manifest_sha256"], "ledger artifact.manifest_sha256")
        manifest_path = repo_file(repo_root, artifact["manifest_path"])
        manifest = validate_manifest(load_json(manifest_path))
        if row["experiment"] != manifest["experiment"]:
            raise ArtifactError(f"ledger experiment differs from manifest: {row.get('run_id')}")
        if row.get("batch_id") != manifest["batch_id"]:
            raise ArtifactError(f"ledger batch_id differs from manifest: {row.get('run_id')}")
        directory = experiment_directory(row["experiment"])
        expected_manifest_path = f"experiments/{directory}/artifacts/{manifest['batch_id']}.json"
        expected_results_path = f"experiments/{directory}/results/{manifest['batch_id']}.json"
        if artifact["manifest_path"] != expected_manifest_path:
            raise ArtifactError(f"ledger manifest path differs from experiment batch: {row.get('run_id')}")
        if row.get("results_path") != expected_results_path:
            raise ArtifactError(f"ledger results path differs from experiment batch: {row.get('run_id')}")
        if expected_repository is not None and manifest["repository"]["name"] != expected_repository:
            raise ArtifactError(f"ledger manifest repository differs: {row.get('run_id')}")
        if artifact["manifest_sha256"] != sha256_file(manifest_path):
            raise ArtifactError(f"ledger manifest SHA-256 differs: {row.get('run_id')}")
        if artifact["archive_sha256"] != manifest["archive"]["sha256"]:
            raise ArtifactError(f"ledger archive SHA-256 differs: {row.get('run_id')}")
        if artifact["release_tag"] != manifest["release"]["tag"]:
            raise ArtifactError(f"ledger release tag differs: {row.get('run_id')}")
        attestations = artifact["attestations"]
        expected_attestations = {
            "archive": {
                "asset_name": manifest["release"]["archive_asset_name"],
                "sha256": manifest["archive"]["sha256"],
            },
            "release": {
                "release_id": artifact["release_id"],
                "repository_id": manifest["repository"]["id"],
                "tag": manifest["release"]["tag"],
            },
        }
        if attestations != expected_attestations:
            raise ArtifactError(f"ledger attestation subjects differ: {row.get('run_id')}")
        results_path = repo_file(repo_root, row.get("results_path"))
        results = load_json(results_path)
        if not isinstance(results, dict) or not isinstance(results.get("lines"), list):
            raise ArtifactError(f"ledger results file is invalid: {row.get('run_id')}")
        if results.get("schema_version") != 2:
            raise ArtifactError(f"ledger results file requires schema_version 2: {row.get('run_id')}")
        if canonical(row) not in {canonical(result) for result in results["lines"]}:
            raise ArtifactError(f"ledger row differs from its compact result: {row.get('run_id')}")
        if verify_remote:
            key = artifact["manifest_path"]
            if key not in remote_receipts:
                remote_receipts[key] = download_and_verify(
                    manifest, manifest_path, expected_repository=expected_repository
                )
            expected_receipt = {**remote_receipts[key], "manifest_path": artifact["manifest_path"]}
            if artifact != expected_receipt:
                raise ArtifactError(f"ledger receipt differs from remote verification: {row.get('run_id')}")
        checked += 1
    if legacy_seen != set(LEGACY_ARTIFACTLESS_RUNS):
        raise ArtifactError("ledger is missing pinned legacy artifactless rows")
    return {"artifact_ledger_rows_verified": checked, "verified": True}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pack_parser = sub.add_parser("pack")
    pack_parser.add_argument("--plan", type=Path, required=True)
    pack_parser.add_argument("--raw-root", type=Path, required=True)
    pack_parser.add_argument("--archive", type=Path, required=True)
    pack_parser.add_argument("--manifest", type=Path, required=True)
    pack_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    verify = sub.add_parser("verify-local")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--archive", type=Path, required=True)
    stage = sub.add_parser("stage-release")
    stage.add_argument("--manifest", type=Path, required=True)
    stage.add_argument("--archive", type=Path, required=True)
    stage.add_argument("--plan", type=Path, required=True)
    stage.add_argument("--raw-root", type=Path, required=True)
    stage.add_argument("--repo-root", type=Path, default=Path.cwd())
    publish = sub.add_parser("publish-release")
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument("--archive", type=Path, required=True)
    publish.add_argument("--plan", type=Path, required=True)
    publish.add_argument("--raw-root", type=Path, required=True)
    publish.add_argument("--repo-root", type=Path, default=Path.cwd())
    publish.add_argument("--confirm-tag", required=True)
    publish.add_argument("--committed-copy", type=Path, required=True)
    remote = sub.add_parser("verify-release")
    remote.add_argument("--manifest", type=Path, required=True)
    remote.add_argument("--expected-repository")
    ledger = sub.add_parser("verify-ledger")
    ledger.add_argument("--repo-root", type=Path, default=Path.cwd())
    ledger.add_argument("--expected-repository")
    ledger.add_argument("--verify-remote", action="store_true")
    ledger.add_argument("--baseline-ledger", type=Path)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "pack":
            result = pack(load_json(args.plan), args.raw_root, args.archive, args.manifest, args.repo_root)
        elif args.command == "verify-local":
            result = verify_local(args.manifest, args.archive)
        elif args.command == "stage-release":
            result = stage_release(
                args.manifest, args.archive, load_json(args.plan), args.raw_root, args.repo_root
            )
        elif args.command == "publish-release":
            result = publish_release(
                args.manifest, args.archive, args.confirm_tag, args.committed_copy,
                load_json(args.plan), args.raw_root, args.repo_root,
            )
        elif args.command == "verify-ledger":
            result = verify_ledger_references(
                args.repo_root, args.expected_repository, verify_remote=args.verify_remote,
                baseline_ledger=args.baseline_ledger,
            )
        else:
            manifest = load_json(args.manifest)
            result = download_and_verify(manifest, args.manifest, args.expected_repository)
        print(json.dumps(result, sort_keys=True, indent=2))
    except ArtifactError as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
