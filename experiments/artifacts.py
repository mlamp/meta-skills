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
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 2
SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
EXPERIMENT_RE = re.compile(r"E-[0-9]+")
MAX_DECODED_STRINGS = 100_000
MAX_DECODED_STRING_BYTES = 64 * 1024 * 1024
LEGACY_ARTIFACTLESS_RUNS = {
    "r-20260817-4cccea322c": ("E-07", "f9d64f749a7fbb2604185f4d6d39085ae51c1b9e88dba80fb210c5a6fb95bc01"),
    "r-20260817-8fbcc01b2b": ("E-07", "0a3ca024718cf8f956bcf74f602962d16e2a15985e666d95381f63331e304bf5"),
    "r-20260817-d4d49120dc": ("E-08", "414664e7bac2606cc61c2f58ae61c492364f905bf375a0cb07deada9a2b52ae7"),
    "r-20260817-48eac1a620": ("E-08", "f12a8ebe27303dec0bac0b1edce133943fe9c7f98ea8e12f524868821211e4a0"),
}
LEGACY_COLD_READER_RUNS = {
    "r-20260821-ff3eb49de8": "0dcd6cc646137b687ed7cd7c415ed4cff04328d3d4d49a04a920e77d9ac20737",
    "r-20260821-96d80e9e72": "f7c7c4c4b6d3f7d2a41ca1e3c50c3531e0448332298f56c24e2ec247b3acf550",
    "r-20260821-2980c491b0": "daa6ef1bd0138cda283f2881cc24b997334e24fbc719b56e71b9dea0667e971d",
    "r-20260821-1c9c2346b7": "9ce352edf499bec37bb17fbef66e5b5146c298916c35780f167f63f379dd10a2",
}


class ArtifactError(RuntimeError):
    pass


def canonical(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ArtifactError("value is not canonical strict JSON") from exc


def reject_json_constant(value):
    raise ArtifactError(f"non-finite JSON number is forbidden: {value}")


def strict_json_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ArtifactError(f"non-finite JSON number is forbidden: {value}")
    return parsed


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result


def strict_json_loads(text: str):
    return json.loads(
        text, parse_constant=reject_json_constant, parse_float=strict_json_float,
        object_pairs_hook=unique_json_object,
    )


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
        return strict_json_loads(path.read_text(encoding="utf-8"))
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
    if "\\" in value or ":" in value:
        raise ArtifactError(f"unsafe artifact member path: {value!r}")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or value != path.as_posix() \
            or any(part in ("", ".", "..") for part in path.parts):
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
    if not isinstance(repository.get("id"), int) or isinstance(repository["id"], bool) \
            or repository["id"] <= 0:
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


def validate_frozen_source_paths(experiment: str, provenance_index: str, policy_source: str):
    if EXPERIMENT_RE.fullmatch(experiment) is None:
        return
    directory = experiment.lower().replace("-", "")
    expected_index = f"experiments/{directory}/freeze.json"
    expected_policy = f"experiments/{directory}/artifact-spec.json"
    if provenance_index != expected_index or policy_source != expected_policy:
        raise ArtifactError("numeric experiment uses noncanonical frozen source paths")


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


def json_strings(value):
    stack = [value]
    decoded_candidates = set()
    seen_containers = set()
    retained_containers = []
    string_count = 0
    string_bytes = 0
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            string_count += 1
            string_bytes += len(current.encode("utf-8"))
            if string_count > MAX_DECODED_STRINGS or string_bytes > MAX_DECODED_STRING_BYTES:
                raise ArtifactError("decoded JSON string scan exceeds the fail-closed resource limit")
            yield current
            candidate = current.strip()
            if candidate[:1] in ("{", "[", '"') and candidate not in decoded_candidates:
                decoded_candidates.add(candidate)
                try:
                    stack.append(strict_json_loads(candidate))
                except json.JSONDecodeError:
                    pass
        elif isinstance(current, dict):
            identity = id(current)
            if identity in seen_containers:
                raise ArtifactError("decoded JSON structure contains a cycle")
            seen_containers.add(identity)
            retained_containers.append(current)
            for key, item in reversed(list(current.items())):
                stack.extend((item, key))
        elif isinstance(current, list):
            identity = id(current)
            if identity in seen_containers:
                raise ArtifactError("decoded JSON structure contains a cycle")
            seen_containers.add(identity)
            retained_containers.append(current)
            stack.extend(reversed(current))


def sanitization_policy(plan):
    return {
        "credential_env_names": plan["credential_env_names"],
        "forbidden_patterns": plan["forbidden_patterns"],
    }


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
                documents = [strict_json_loads(text)]
            elif relative.endswith(".jsonl"):
                documents = []
                for number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        documents.append(strict_json_loads(line))
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
        "policy_sha256": sha256_bytes(canonical(sanitization_policy(plan)).encode()),
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
        "freeze_sha256", "packager_commit", "provenance", "provenance_index",
        "sanitization_policy_source", "schedule", "release",
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
    provenance_index = safe_relative(plan["provenance_index"]).as_posix()
    policy_source = safe_relative(plan["sanitization_policy_source"]).as_posix()
    validate_frozen_source_paths(plan["experiment"], provenance_index, policy_source)
    if provenance_index not in plan["provenance"] or policy_source not in plan["provenance"]:
        raise ArtifactError("provenance must contain its index and sanitization policy source")
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
        "packager_commit", "provenance", "provenance_index", "sanitization_policy_source",
        "schedule", "release", "supersedes", "exclusions", "execution",
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
    provenance_index = safe_relative(manifest["provenance_index"]).as_posix()
    policy_source = safe_relative(manifest["sanitization_policy_source"]).as_posix()
    validate_frozen_source_paths(manifest["experiment"], provenance_index, policy_source)
    if provenance_index not in manifest["provenance"] or policy_source not in manifest["provenance"]:
        raise ArtifactError("provenance must contain its index and sanitization policy source")
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
        "exact_secret_scan", "files_scanned", "forbidden_pattern_ids", "policy_sha256", "scanned_bytes",
        "status", "report_sha256",
    }
    if not isinstance(sanitization, dict) or set(sanitization) != required_scan or sanitization.get("status") != "passed":
        raise ArtifactError("manifest sanitization report is invalid")
    report = {key: value for key, value in sanitization.items() if key != "report_sha256"}
    require_sha256(sanitization["report_sha256"], "sanitization.report_sha256")
    if sanitization["report_sha256"] != sha256_bytes(canonical(report).encode()):
        raise ArtifactError("sanitization report digest is invalid")
    require_sha256(sanitization["policy_sha256"], "sanitization.policy_sha256")
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
        "provenance_index": plan["provenance_index"],
        "sanitization_policy_source": plan["sanitization_policy_source"],
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
    contents = {}
    order = []
    try:
        with archive_path.open("rb") as raw:
            header = raw.read(10)
        if header != b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff":
            raise ArtifactError("gzip header does not match level-9 deterministic contract")
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for info in archive:
                safe_relative(info.name)
                order.append(info.name)
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
                contents[info.name] = data
                seen[info.name] = {"bytes": len(data), "sha256": sha256_bytes(data)}
    except (tarfile.TarError, OSError) as exc:
        raise ArtifactError("cannot read archive") from exc
    if order != sorted(expected):
        raise ArtifactError("archive member order is not the sorted manifest order")
    if set(seen) != set(expected):
        raise ArtifactError("archive members differ from manifest")
    for path, values in seen.items():
        if values["bytes"] != expected[path].get("bytes") or values["sha256"] != expected[path].get("sha256"):
            raise ArtifactError(f"archive member differs from manifest: {path}")
    with tempfile.TemporaryDirectory() as temporary:
        canonical_archive = Path(temporary) / "canonical.tar.gz"
        create_archive(contents, sorted(expected), canonical_archive)
        if canonical_archive.stat().st_size != archive_path.stat().st_size \
                or sha256_file(canonical_archive) != sha256_file(archive_path):
            raise ArtifactError("archive bytes differ from the deterministic packer output")
    return manifest


def verify_source(manifest_path: Path, plan, raw_root: Path, repo_root: Path):
    validate_plan(plan)
    raw_root = validate_raw_root(plan, raw_root, repo_root)
    manifest = validate_manifest(load_json(manifest_path))
    expected_fields = (
        "repository", "experiment", "batch_id", "raw_root", "frozen_commit", "freeze_sha256",
        "packager_commit", "provenance", "provenance_index", "sanitization_policy_source",
        "schedule", "release", "supersedes", "exclusions", "execution",
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


def verify_trusted_plan(plan, repo_root: Path):
    """Require numeric experiments to reproduce their plan from frozen code."""
    validate_plan(plan)
    experiment = plan["experiment"]
    trusted_sources = {
        "experiments/e09/freeze.json": ("E-09", "experiments/e09/harness.py"),
    }
    trusted = trusted_sources.get(plan["provenance_index"])
    if trusted is None:
        if EXPERIMENT_RE.fullmatch(experiment) is None:
            return
        raise ArtifactError(f"numeric experiment has no trusted plan derivation: {experiment}")
    expected_experiment, harness_relative = trusted
    if experiment != expected_experiment:
        raise ArtifactError("trusted experiment provenance is paired with the wrong experiment id")
    harness = repo_file(repo_root, harness_relative)
    command = [sys.executable, str(harness), "artifact-plan-json"]
    if plan.get("supersedes") is not None:
        command.extend(("--supersedes", plan["supersedes"]))
    output = run(command, cwd=repo_root, timeout=300)
    try:
        derived = strict_json_loads(output)
    except json.JSONDecodeError as exc:
        raise ArtifactError("frozen experiment harness returned an invalid artifact plan") from exc
    validate_plan(derived)
    if derived != plan:
        raise ArtifactError("saved artifact plan differs from the frozen harness derivation")


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
        return strict_json_loads(output)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"GitHub returned invalid JSON for {endpoint}") from exc


def gh_paginated_json(repo: str, endpoint: str):
    resource = f"repos/{repo}/{endpoint}"
    output = run(["gh", "api", "--paginate", "--slurp", resource])
    try:
        pages = strict_json_loads(output)
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


def committed_file_bytes(repo_root: Path, commit: str, relative: str) -> bytes:
    safe_relative(relative)
    try:
        process = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{relative}"],
            capture_output=True, timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise ArtifactError(f"timed out reading frozen file from Git: {relative}") from exc
    if process.returncode:
        raise ArtifactError(f"frozen commit does not contain provenance file: {relative}")
    return process.stdout


def committed_file_sha256(repo_root: Path, commit: str, relative: str) -> str:
    return sha256_bytes(committed_file_bytes(repo_root, commit, relative))


def require_local_frozen_source(repo_root: Path, manifest):
    root = repo_root.resolve(strict=True)
    head = run(["git", "-C", str(root), "rev-parse", "HEAD"])
    frozen_commit = manifest["frozen_commit"]
    if head != frozen_commit:
        raise ArtifactError("local HEAD must equal frozen_commit")
    provenance = dict(manifest["provenance"])
    provenance_index = manifest["provenance_index"]
    index_bytes = committed_file_bytes(root, frozen_commit, provenance_index)
    index_sha256 = sha256_bytes(index_bytes)
    if manifest["freeze_sha256"] != index_sha256:
        raise ArtifactError("manifest freeze_sha256 differs from the frozen provenance index")
    try:
        index = strict_json_loads(index_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ArtifactError("frozen provenance index is not valid JSON") from exc
    frozen_files = index.get("files") if isinstance(index, dict) else None
    validate_hash_map(frozen_files, "frozen provenance index files")
    expected_provenance = {**frozen_files, provenance_index: index_sha256}
    if provenance != expected_provenance:
        raise ArtifactError("manifest provenance differs from the frozen provenance index")
    policy_source = manifest["sanitization_policy_source"]
    try:
        policy_document = strict_json_loads(committed_file_bytes(root, frozen_commit, policy_source))
        expected_policy = {
            "credential_env_names": policy_document["credential_env_names"],
            "forbidden_patterns": policy_document["forbidden_patterns"],
        }
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        raise ArtifactError("frozen sanitization policy source is invalid") from exc
    expected_policy_sha256 = sha256_bytes(canonical(expected_policy).encode())
    if manifest["sanitization"]["policy_sha256"] != expected_policy_sha256:
        raise ArtifactError("manifest sanitizer policy differs from the frozen policy source")
    try:
        packager_relative = Path(__file__).resolve(strict=True).relative_to(root).as_posix()
    except ValueError as exc:
        raise ArtifactError("running packager is outside repo_root") from exc
    paths = set(provenance) | {packager_relative}
    for relative in sorted(paths):
        committed_sha256 = committed_file_sha256(root, frozen_commit, relative)
        if relative in provenance and provenance[relative] != committed_sha256:
            raise ArtifactError(f"manifest provenance differs from frozen commit: {relative}")
        current = repo_file(root, relative)
        if sha256_file(current) != committed_sha256:
            raise ArtifactError(f"working file differs from frozen commit: {relative}")


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
    require_local_frozen_source(repo_root, manifest)
    verify_trusted_plan(plan, repo_root)
    verify_source(manifest_path, plan, raw_root, repo_root)
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
    commit = existing_tag_commit(repo, tag)
    if commit is None:
        raise ArtifactError(f"tag does not exist: {tag}")
    return commit


def resolve_git_target(repo: str, target) -> str:
    for _ in range(3):
        if target.get("type") == "commit":
            return target["sha"]
        if target.get("type") != "tag":
            break
        target = gh_json(repo, f"git/tags/{target['sha']}")["object"]
    raise ArtifactError("tag does not resolve to a commit")


def existing_tag_commit(repo: str, tag: str) -> str | None:
    refs = gh_paginated_json(repo, f"git/matching-refs/tags/{tag}?per_page=100")
    exact = [row for row in refs if row.get("ref") == f"refs/tags/{tag}"]
    if len(exact) > 1:
        raise ArtifactError(f"multiple exact tag refs exist: {tag}")
    if not exact:
        return None
    return resolve_git_target(repo, exact[0].get("object", {}))


def download_and_verify(
    manifest: dict, committed_manifest: Path | None = None, expected_repository: str | None = None
):
    if committed_manifest is not None:
        require_regular_file(committed_manifest, "committed manifest")
    validate_manifest(manifest)
    repo = manifest["repository"]["name"]
    if expected_repository is not None and repo != expected_repository:
        raise ArtifactError(
            f"manifest repository differs from verifier repository; expected={expected_repository}, actual={repo}"
        )
    tag = manifest["release"]["tag"]
    repository = verify_repository_identity(manifest)
    commit_is_on_default_branch(repo, manifest["frozen_commit"], repository)
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
        source_manifest_sha256 = sha256_file(source_manifest)
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
        "manifest_sha256": source_manifest_sha256,
        "release_id": release["id"],
        "release_tag": tag,
        "verified": True,
    }


def publish_release(
    manifest_path: Path, archive_path: Path, confirm_tag: str, committed_copy: Path,
    plan, raw_root: Path, repo_root: Path,
):
    manifest = verify_local(manifest_path, archive_path)
    require_local_frozen_source(repo_root, manifest)
    verify_trusted_plan(plan, repo_root)
    verify_source(manifest_path, plan, raw_root, repo_root)
    repo = manifest["repository"]["name"]
    tag = manifest["release"]["tag"]
    if confirm_tag != tag:
        raise ArtifactError("--confirm-tag must exactly match the manifest tag")
    committed_copy = preflight_committed_copy(manifest_path, committed_copy, repo_root)
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
        tag_commit = existing_tag_commit(repo, tag)
        if tag_commit is not None and tag_commit != manifest["frozen_commit"]:
            raise ArtifactError("existing release tag points to the wrong commit")
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


def preflight_committed_copy(source: Path, target: Path, repo_root: Path) -> Path:
    require_regular_file(source, "source manifest")
    lexical_root = Path(os.path.abspath(repo_root))
    root = repo_root.resolve(strict=True)
    lexical_candidate = target if target.is_absolute() else lexical_root / target
    lexical_candidate = Path(os.path.abspath(lexical_candidate))
    try:
        relative = lexical_candidate.relative_to(lexical_root)
    except ValueError as exc:
        try:
            relative = lexical_candidate.relative_to(root)
        except ValueError:
            raise ArtifactError("committed manifest path must be beneath repo_root") from exc
    unresolved = lexical_root
    for part in relative.parts[:-1]:
        unresolved = unresolved / part
        if unresolved.is_symlink():
            raise ArtifactError("committed manifest path contains a symlink")
    candidate = root / relative
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        candidate.parent.resolve(strict=True).relative_to(root)
    except ValueError as exc:
        raise ArtifactError("committed manifest parent escapes repo_root") from exc
    if candidate.exists() or candidate.is_symlink():
        require_regular_file(candidate, "committed manifest")
        if candidate.read_bytes() != source.read_bytes():
            raise ArtifactError(f"committed manifest differs: {candidate}")
    return candidate


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
            row = strict_json_loads(line)
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


def require_manifest_list_membership(path: Path, relative: str):
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ArtifactError(f"cannot read verified manifest list: {path}") from exc
    if data:
        if not data.endswith(b"\0"):
            raise ArtifactError("verified manifest list is not NUL-terminated")
        entries = data.split(b"\0")[:-1]
    else:
        entries = []
    if any(not entry for entry in entries) or len(entries) != len(set(entries)):
        raise ArtifactError("verified manifest list contains an invalid or duplicate entry")
    if os.fsencode(relative) not in set(entries):
        raise ArtifactError("manifest was not verified through the ledger")
    return {"manifest_path": relative, "verified_through_ledger": True}


def require_exact_keys(value, expected, label: str):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ArtifactError(f"{label} has the wrong fields")


def require_nonnegative_int(value, label: str):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ArtifactError(f"{label} must be a nonnegative integer")


def require_number(value, label: str, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ArtifactError(f"{label} must be a finite number")


def require_bool(value, label: str):
    if not isinstance(value, bool):
        raise ArtifactError(f"{label} must be a boolean")


def require_string_list(value, label: str, sorted_unique=False):
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ArtifactError(f"{label} must be a list of strings")
    if sorted_unique and value != sorted(set(value)):
        raise ArtifactError(f"{label} must be sorted and unique")


def validate_stats(value, label: str, nullable=False):
    if nullable and value is None:
        return
    require_exact_keys(
        value, {"n", "values", "mean", "sample_variance", "sample_stdev"}, label
    )
    require_nonnegative_int(value["n"], f"{label} n")
    if not isinstance(value["values"], list) or not value["values"] \
            or value["n"] != len(value["values"]):
        raise ArtifactError(f"{label} values differ from n")
    for item in value["values"]:
        require_number(item, f"{label} value")
    for field in ("mean", "sample_variance", "sample_stdev"):
        require_number(value[field], f"{label} {field}")
    expected = {
        "mean": statistics.mean(value["values"]),
        "sample_variance": statistics.variance(value["values"])
        if value["n"] > 1 else 0,
        "sample_stdev": statistics.stdev(value["values"])
        if value["n"] > 1 else 0,
    }
    if any(value[field] != expected[field] for field in expected):
        raise ArtifactError(f"{label} statistics differ from values")


def validate_pooled_rate(value, label: str):
    require_exact_keys(value, {"hits", "tokens", "rate_per_1000"}, label)
    require_nonnegative_int(value["hits"], f"{label} hits")
    require_nonnegative_int(value["tokens"], f"{label} tokens")
    require_number(value["rate_per_1000"], f"{label} rate_per_1000", nullable=True)
    expected = 1000 * value["hits"] / value["tokens"] if value["tokens"] else None
    if value["rate_per_1000"] != expected:
        raise ArtifactError(f"{label} rate differs from hits and tokens")


def require_stats_values(value, expected, label: str):
    if expected:
        validate_stats(value, label)
        if value["values"] != expected:
            raise ArtifactError(f"{label} values differ from runs")
    elif value is not None:
        raise ArtifactError(f"{label} must be null without usable runs")


def require_pooled_values(value, records, hits_key, label: str):
    usable = [record for record in records if record["output_tokens"] and record[hits_key] is not None]
    expected_hits = sum(record[hits_key] for record in usable)
    expected_tokens = sum(record["output_tokens"] for record in usable)
    validate_pooled_rate(value, label)
    if value["hits"] != expected_hits or value["tokens"] != expected_tokens:
        raise ArtifactError(f"{label} totals differ from runs")


def validate_condition_summary(value, label: str):
    required = {
        "task_failures", "listed_hits", "listed_rate_per_1000", "listed_pooled",
        "substitute_hits", "substitute_rate_per_1000", "substitute_pooled",
    }
    require_exact_keys(value, required, label)
    validate_stats(value["task_failures"], f"{label} task_failures")
    validate_stats(value["listed_hits"], f"{label} listed_hits")
    validate_stats(value["listed_rate_per_1000"], f"{label} listed_rate_per_1000", nullable=True)
    validate_pooled_rate(value["listed_pooled"], f"{label} listed_pooled")
    validate_stats(value["substitute_hits"], f"{label} substitute_hits", nullable=True)
    validate_stats(
        value["substitute_rate_per_1000"], f"{label} substitute_rate_per_1000", nullable=True
    )
    validate_pooled_rate(value["substitute_pooled"], f"{label} substitute_pooled")


def require_canonical_utc(value, label: str):
    if not isinstance(value, str):
        raise ArtifactError(f"{label} must be canonical UTC")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ArtifactError(f"{label} must be canonical UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed) \
            or parsed.isoformat(timespec="seconds") != value:
        raise ArtifactError(f"{label} must be canonical UTC")
    return parsed


def content_run_id(payload, completed_at: str) -> str:
    return "r-" + completed_at[:10].replace("-", "") + "-" \
        + sha256_bytes(canonical(payload).encode())[:10]


def qualification_assertion_count(suite) -> int:
    per_rep = 0
    for case in suite["qualification"]["cases"]:
        if case.get("kind") == "semantics":
            per_rep += 1 + 5 + len(case["expected"]["sublabels"])
        else:
            per_rep += 2 + sum(len(row) - 1 for row in case["expected"])
    return per_rep * suite["qualification"]["repetitions_per_profile"]


def validate_cold_reader_qualification_row(
    row, repo_root: Path, require_current_inputs=False
):
    required = {
        "run_id", "date", "schema_version", "type", "experiment", "family", "tier", "passed",
        "started_calls", "assertions", "failed_assertions", "errors", "key", "raw_dir", "completed_at",
    }
    require_exact_keys(row, required, "cold-reader qualification row")
    if row["schema_version"] != 2 or row["type"] != "experiment" \
            or row["experiment"] != "E-09-cold-reader" or row["tier"] != "qualification":
        raise ArtifactError("cold-reader qualification discriminator is invalid")
    profile_name = row["family"]
    if not isinstance(profile_name, str) or not profile_name:
        raise ArtifactError("cold-reader qualification family is invalid")
    require_exact_keys(
        row["key"],
        {
            "tier", "profile", "profile_sha256", "harness_sha256", "catalog_sha256",
            "suite_sha256", "freeze_sha256",
        },
        "cold-reader qualification key",
    )
    if row["key"]["tier"] != "qualification" or row["key"]["profile"] != profile_name:
        raise ArtifactError("cold-reader qualification key discriminator is invalid")
    for field in (
        "profile_sha256", "harness_sha256", "catalog_sha256", "suite_sha256", "freeze_sha256",
    ):
        require_sha256(row["key"][field], f"cold-reader qualification key {field}")
    harness = repo_file(repo_root, "experiments/e09/harness.py")
    catalog = repo_file(repo_root, "experiments/e09/catalog.json")
    suite_path = repo_file(repo_root, "experiments/e09/cold_reader_cases.json")
    freeze = repo_file(repo_root, "experiments/e09/freeze.json")
    for field in ("started_calls", "assertions", "failed_assertions", "errors"):
        require_nonnegative_int(row[field], f"cold-reader qualification {field}")
    if row["failed_assertions"] > row["assertions"] or row["errors"] > row["started_calls"]:
        raise ArtifactError("cold-reader qualification counts are impossible")
    current_freeze = sha256_file(freeze)
    models = load_json(repo_file(repo_root, "experiments/e09/models.json"))
    profile = models.get("profiles", {}).get(profile_name)
    current_key = None
    if profile_name in models.get("qualification_profiles", []) \
            and isinstance(profile, dict) and profile.get("role") == "cold_reader":
        current_key = {
            "tier": "qualification",
            "profile": profile_name,
            "profile_sha256": sha256_bytes(canonical(profile).encode()),
            "harness_sha256": sha256_file(harness),
            "catalog_sha256": sha256_file(catalog),
            "suite_sha256": sha256_file(suite_path),
            "freeze_sha256": current_freeze,
        }
    is_current = row["key"] == current_key
    if require_current_inputs and not is_current:
        raise ArtifactError("new cold-reader qualification row does not bind the current inputs")
    if is_current:
        suite = load_json(suite_path)
        expected_calls = len(suite["qualification"]["cases"]) \
            * suite["qualification"]["repetitions_per_profile"]
        expected_assertions = qualification_assertion_count(suite)
        if row["started_calls"] != expected_calls or row["assertions"] > expected_assertions:
            raise ArtifactError("cold-reader qualification counts differ from the current suite")
        expected_pass = row["errors"] == 0 and row["failed_assertions"] == 0 \
            and row["assertions"] == expected_assertions
        if not isinstance(row["passed"], bool) or row["passed"] != expected_pass:
            raise ArtifactError("cold-reader qualification pass flag differs from its counts")
    elif not isinstance(row["passed"], bool) or row["passed"] \
            != (row["errors"] == 0 and row["failed_assertions"] == 0 and row["assertions"] > 0):
        raise ArtifactError("historical cold-reader pass flag differs from its counts")
    completed_at = row["completed_at"]
    require_canonical_utc(completed_at, "cold-reader qualification completed_at")
    if row["date"] != completed_at:
        raise ArtifactError("cold-reader qualification date differs from completed_at")
    expected_raw = "experiments/e09/raw/qualification/cr-" \
        + sha256_bytes(canonical(row["key"]).encode())[:16]
    if row["raw_dir"] != expected_raw:
        raise ArtifactError("cold-reader qualification raw_dir differs from its key")
    payload = {key: value for key, value in row.items() if key not in ("run_id", "date")}
    if row["run_id"] != content_run_id(payload, completed_at):
        raise ArtifactError("cold-reader qualification run_id differs from its content")


def validate_e09_result_row(row, manifest):
    required = {
        "run_id", "date", "schema_version", "type", "experiment", "batch_id", "family", "arms",
        "claim_checks", "judge_agreement", "reps_per_arm", "sample_variance", "seed", "judge_seed",
        "artifact", "results_path", "freeze_sha256", "completed_at",
    }
    require_exact_keys(row, required, "E-09 result row")
    if row["schema_version"] != 2 or row["type"] != "experiment" or row["experiment"] != "E-09":
        raise ArtifactError("E-09 result discriminator is invalid")
    if row["experiment"] != manifest.get("experiment") \
            or row["batch_id"] != manifest.get("batch_id") \
            or row["freeze_sha256"] != manifest.get("freeze_sha256"):
        raise ArtifactError("E-09 result identity differs from its manifest")
    if row["family"] not in ("fable-subject", "kimi-subject") or row["reps_per_arm"] != 5 \
            or row["sample_variance"] != "n-1" or row["seed"] != 20260821 \
            or row["judge_seed"] != 20260822:
        raise ArtifactError("E-09 result frozen constants differ")
    require_exact_keys(row["arms"], {"control", "treatment"}, "E-09 arms")
    arm_fields = {
        "runs", "selected_relevant", "coverage", "selection_precision", "irrelevant_selections",
        "irrelevant_selection_median", "contract_tokens", "coverage_per_100_contract_tokens",
        "suppression", "no_suppression", "substitute_paired_raw_difference",
        "substitute_paired_rate_difference", "over_cap_count", "contract_violation_count",
        "interview_error_count",
    }
    run_fields = {
        "rep", "selected_ids", "automatic_bans", "selected_relevant", "coverage",
        "selection_precision", "irrelevant_selections", "contract_tokens", "over_cap",
        "contract_violations", "interview_status", "coverage_per_100_contract_tokens",
        "rendered_relevant",
        "catalog_rules_removed_in_no_suppression", "catalog_rule_tokens_removed_in_no_suppression",
        "conditions",
    }
    condition_fields = {
        "task_successes", "task_failures", "task_judge_errors", "listed_hits", "output_tokens",
        "listed_rate_per_1000", "substitute_hits", "substitute_rate_per_1000", "substitute_buckets",
        "outside_selected_substitute_candidates", "substitute_judgment_complete",
    }
    relevant_ids = {"U01", "U03", "U05", "U06"}
    catalog_ids = {f"U{number:02d}" for number in range(1, 7)}
    for arm_name, arm in row["arms"].items():
        require_exact_keys(arm, arm_fields, f"E-09 {arm_name} arm")
        runs = arm["runs"]
        if not isinstance(runs, list) or len(runs) != 5 \
                or [run.get("rep") for run in runs if isinstance(run, dict)] != [1, 2, 3, 4, 5]:
            raise ArtifactError(f"E-09 {arm_name} arm requires five distinct repetitions")
        for run in runs:
            require_exact_keys(run, run_fields, f"E-09 {arm_name} run")
            require_nonnegative_int(run["rep"], f"E-09 {arm_name} rep")
            require_string_list(
                run["selected_ids"], f"E-09 {arm_name} selected_ids", sorted_unique=True
            )
            require_string_list(
                run["automatic_bans"], f"E-09 {arm_name} automatic_bans", sorted_unique=True
            )
            selected = set(run["selected_ids"])
            automatic = set(run["automatic_bans"])
            if not selected <= catalog_ids or not automatic <= catalog_ids \
                    or (arm_name == "control" and automatic):
                raise ArtifactError(f"E-09 {arm_name} catalog selections are invalid")
            require_nonnegative_int(run["selected_relevant"], f"E-09 {arm_name} selected_relevant")
            require_number(run["coverage"], f"E-09 {arm_name} coverage")
            require_number(run["selection_precision"], f"E-09 {arm_name} selection_precision")
            require_nonnegative_int(
                run["irrelevant_selections"], f"E-09 {arm_name} irrelevant_selections"
            )
            require_nonnegative_int(run["contract_tokens"], f"E-09 {arm_name} contract_tokens")
            require_bool(run["over_cap"], f"E-09 {arm_name} over_cap")
            require_string_list(run["contract_violations"], f"E-09 {arm_name} contract_violations")
            if not isinstance(run["interview_status"], str) or not run["interview_status"]:
                raise ArtifactError(f"E-09 {arm_name} interview_status must be a non-empty string")
            require_number(
                run["coverage_per_100_contract_tokens"],
                f"E-09 {arm_name} coverage_per_100_contract_tokens",
            )
            require_nonnegative_int(
                run["rendered_relevant"], f"E-09 {arm_name} rendered_relevant"
            )
            require_nonnegative_int(
                run["catalog_rules_removed_in_no_suppression"],
                f"E-09 {arm_name} catalog_rules_removed_in_no_suppression",
            )
            require_nonnegative_int(
                run["catalog_rule_tokens_removed_in_no_suppression"],
                f"E-09 {arm_name} catalog_rule_tokens_removed_in_no_suppression",
            )
            expected_selected_relevant = len(selected & relevant_ids)
            all_selected = selected | automatic
            if run["selected_relevant"] != expected_selected_relevant \
                    or run["coverage"] != expected_selected_relevant / len(relevant_ids) \
                    or run["selection_precision"] != (
                        expected_selected_relevant / len(all_selected) if all_selected else 1.0
                    ) \
                    or run["irrelevant_selections"] != len((selected - relevant_ids) | automatic) \
                    or run["over_cap"] != (run["contract_tokens"] > 60) \
                    or run["rendered_relevant"] > run["selected_relevant"] \
                    or run["coverage_per_100_contract_tokens"] != (
                        100 * run["rendered_relevant"] / run["contract_tokens"]
                        if run["contract_tokens"] else 0
                    ):
                raise ArtifactError(f"E-09 {arm_name} run metrics differ from selections")
            if arm_name == "control" and (
                run["catalog_rules_removed_in_no_suppression"] != 0
                or run["catalog_rule_tokens_removed_in_no_suppression"] != 0
            ):
                raise ArtifactError("E-09 control run carries treatment-only removal metrics")
            expected_conditions = {"suppression", "no_suppression"} \
                if arm_name == "treatment" else {"suppression"}
            require_exact_keys(run["conditions"], expected_conditions, f"E-09 {arm_name} conditions")
            for condition in run["conditions"].values():
                require_exact_keys(condition, condition_fields, "E-09 task condition")
                for field in (
                    "task_successes", "task_failures", "task_judge_errors", "listed_hits",
                    "output_tokens",
                ):
                    require_nonnegative_int(condition[field], f"E-09 task condition {field}")
                require_number(
                    condition["listed_rate_per_1000"],
                    "E-09 task condition listed_rate_per_1000",
                    nullable=True,
                )
                if condition["substitute_hits"] is not None:
                    require_nonnegative_int(
                        condition["substitute_hits"], "E-09 task condition substitute_hits"
                    )
                require_number(
                    condition["substitute_rate_per_1000"],
                    "E-09 task condition substitute_rate_per_1000",
                    nullable=True,
                )
                require_exact_keys(
                    condition["substitute_buckets"], {"unaided_only", "catalog_mapped_only", "both"},
                    "E-09 substitute buckets",
                )
                for value in condition["substitute_buckets"].values():
                    require_nonnegative_int(value, "E-09 substitute bucket")
                if condition["outside_selected_substitute_candidates"] is not None:
                    require_nonnegative_int(
                        condition["outside_selected_substitute_candidates"],
                        "E-09 outside-selected substitute candidates",
                    )
                require_bool(
                    condition["substitute_judgment_complete"],
                    "E-09 substitute_judgment_complete",
                )
                if condition["task_successes"] + condition["task_failures"] != 4 \
                        or condition["task_judge_errors"] > 4:
                    raise ArtifactError("E-09 task condition task counts are impossible")
                task_outputs_complete = condition["listed_rate_per_1000"] is not None
                expected_listed_rate = 1000 * condition["listed_hits"] / condition["output_tokens"] \
                    if condition["output_tokens"] and task_outputs_complete else None
                if condition["listed_rate_per_1000"] != expected_listed_rate:
                    raise ArtifactError("E-09 listed rate differs from hits and tokens")
                substitute_complete = condition["substitute_judgment_complete"]
                if substitute_complete != (condition["substitute_hits"] is not None) \
                        or substitute_complete != (
                            condition["outside_selected_substitute_candidates"] is not None
                        ):
                    raise ArtifactError("E-09 substitute completeness differs from its metrics")
                expected_substitute_rate = 1000 * condition["substitute_hits"] / condition["output_tokens"] \
                    if condition["output_tokens"] and substitute_complete else None
                if condition["substitute_rate_per_1000"] != expected_substitute_rate:
                    raise ArtifactError("E-09 substitute rate differs from hits and tokens")
                if substitute_complete and sum(condition["substitute_buckets"].values()) \
                        != condition["substitute_hits"]:
                    raise ArtifactError("E-09 substitute buckets differ from substitute_hits")
        for field in (
            "selected_relevant", "coverage", "selection_precision", "irrelevant_selections",
            "contract_tokens", "coverage_per_100_contract_tokens",
        ):
            require_stats_values(
                arm[field], [run[field] for run in runs], f"E-09 {arm_name} {field}"
            )
        require_number(
            arm["irrelevant_selection_median"], f"E-09 {arm_name} irrelevant_selection_median"
        )
        if arm["irrelevant_selection_median"] != statistics.median(
            run["irrelevant_selections"] for run in runs
        ):
            raise ArtifactError(f"E-09 {arm_name} irrelevant median differs from runs")
        validate_condition_summary(arm["suppression"], f"E-09 {arm_name} suppression")
        suppression_runs = [run["conditions"]["suppression"] for run in runs]
        for field in ("task_failures", "listed_hits", "listed_rate_per_1000",
                      "substitute_hits", "substitute_rate_per_1000"):
            require_stats_values(
                arm["suppression"][field],
                [condition[field] for condition in suppression_runs if condition[field] is not None],
                f"E-09 {arm_name} suppression {field}",
            )
        require_pooled_values(
            arm["suppression"]["listed_pooled"], suppression_runs, "listed_hits",
            f"E-09 {arm_name} suppression listed_pooled",
        )
        require_pooled_values(
            arm["suppression"]["substitute_pooled"], suppression_runs, "substitute_hits",
            f"E-09 {arm_name} suppression substitute_pooled",
        )
        if arm_name == "treatment":
            validate_condition_summary(
                arm["no_suppression"], f"E-09 {arm_name} no_suppression"
            )
            no_suppression_runs = [run["conditions"]["no_suppression"] for run in runs]
            for field in ("task_failures", "listed_hits", "listed_rate_per_1000",
                          "substitute_hits", "substitute_rate_per_1000"):
                require_stats_values(
                    arm["no_suppression"][field],
                    [condition[field] for condition in no_suppression_runs if condition[field] is not None],
                    f"E-09 {arm_name} no_suppression {field}",
                )
            require_pooled_values(
                arm["no_suppression"]["listed_pooled"], no_suppression_runs, "listed_hits",
                f"E-09 {arm_name} no_suppression listed_pooled",
            )
            require_pooled_values(
                arm["no_suppression"]["substitute_pooled"], no_suppression_runs, "substitute_hits",
                f"E-09 {arm_name} no_suppression substitute_pooled",
            )
            paired_raw = [
                suppression["substitute_hits"] - no_suppression["substitute_hits"]
                for suppression, no_suppression in zip(suppression_runs, no_suppression_runs)
                if suppression["substitute_hits"] is not None
                and no_suppression["substitute_hits"] is not None
            ]
            paired_rate = [
                suppression["substitute_rate_per_1000"]
                - no_suppression["substitute_rate_per_1000"]
                for suppression, no_suppression in zip(suppression_runs, no_suppression_runs)
                if suppression["substitute_rate_per_1000"] is not None
                and no_suppression["substitute_rate_per_1000"] is not None
            ]
        else:
            paired_raw = []
            paired_rate = []
        require_stats_values(
            arm["substitute_paired_raw_difference"], paired_raw,
            f"E-09 {arm_name} substitute_paired_raw_difference",
        )
        require_stats_values(
            arm["substitute_paired_rate_difference"], paired_rate,
            f"E-09 {arm_name} substitute_paired_rate_difference",
        )
        for field in ("over_cap_count", "contract_violation_count", "interview_error_count"):
            require_nonnegative_int(arm[field], f"E-09 {arm_name} {field}")
        expected_counts = {
            "over_cap_count": sum(run["over_cap"] for run in runs),
            "contract_violation_count": sum(bool(run["contract_violations"]) for run in runs),
            "interview_error_count": sum(run["interview_status"] != "ok" for run in runs),
        }
        if any(arm[field] != expected for field, expected in expected_counts.items()):
            raise ArtifactError(f"E-09 {arm_name} counts differ from runs")
        if (arm_name == "control") != (arm["no_suppression"] is None):
            raise ArtifactError("E-09 no_suppression summary differs from arm")
    require_exact_keys(row["claim_checks"], {"C19", "C20", "C21", "C22"}, "E-09 claim checks")
    claim_fields = {
        "C19": {"status", "mean_gain", "ceiling_blocks_one_pattern_gain", "passes_screen"},
        "C20": {"status", "all_task_judgments_complete", "density_not_lower",
                "irrelevant_median_at_most_one", "task_failure_increase_at_most_one"},
        "C21": {"status", "all_five_rates", "all_five_pairs_remove_catalog_rules",
                "raw_higher", "rate_higher"},
        "C22": {"status", "all_five_rates", "treatment_rate_lower"},
    }
    for claim, fields in claim_fields.items():
        require_exact_keys(row["claim_checks"][claim], fields, f"E-09 {claim}")
        if row["claim_checks"][claim]["status"] not in ("pass", "fail", "incomplete", "not_testable"):
            raise ArtifactError(f"E-09 {claim} status is invalid")
        for field, value in row["claim_checks"][claim].items():
            if field == "status":
                continue
            if field == "mean_gain":
                require_number(value, f"E-09 {claim} {field}")
            else:
                require_bool(value, f"E-09 {claim} {field}")
    control = row["arms"]["control"]
    treatment = row["arms"]["treatment"]
    all_interviews_ok = all(
        arm["interview_error_count"] == 0 and arm["over_cap_count"] == 0
        and arm["contract_violation_count"] == 0
        for arm in (control, treatment)
    )
    mean_gain = treatment["selected_relevant"]["mean"] - control["selected_relevant"]["mean"]
    ceiling_blocked = len(relevant_ids) - control["selected_relevant"]["mean"] < 1
    judgments_complete = all(
        run["conditions"]["suppression"]["task_judge_errors"] == 0
        for run in control["runs"] + treatment["runs"]
    )
    density_not_lower = treatment["coverage_per_100_contract_tokens"]["mean"] \
        >= control["coverage_per_100_contract_tokens"]["mean"]
    irrelevant_median_ok = treatment["irrelevant_selection_median"] <= 1
    task_failure_ok = treatment["suppression"]["task_failures"]["mean"] \
        - control["suppression"]["task_failures"]["mean"] <= 1
    c20_complete = all_interviews_ok and judgments_complete
    paired_raw = treatment["substitute_paired_raw_difference"]
    paired_rate = treatment["substitute_paired_rate_difference"]
    c21_has_contrast = all(
        run["catalog_rules_removed_in_no_suppression"] >= 1 for run in treatment["runs"]
    )
    c21_complete = all_interviews_ok and paired_raw is not None and paired_raw["n"] == 5 \
        and paired_rate is not None and paired_rate["n"] == 5 and c21_has_contrast
    treatment_listed = treatment["suppression"]["listed_rate_per_1000"]
    control_listed = control["suppression"]["listed_rate_per_1000"]
    c22_complete = all_interviews_ok and treatment_listed is not None \
        and treatment_listed["n"] == 5 and control_listed is not None \
        and control_listed["n"] == 5

    def expected_status(complete, passes, not_testable=False):
        if not complete:
            return "incomplete"
        if not_testable:
            return "not_testable"
        return "pass" if passes else "fail"

    expected_claims = {
        "C19": {
            "status": expected_status(all_interviews_ok, mean_gain >= 1, ceiling_blocked),
            "mean_gain": mean_gain,
            "ceiling_blocks_one_pattern_gain": ceiling_blocked,
            "passes_screen": all_interviews_ok and not ceiling_blocked and mean_gain >= 1,
        },
        "C20": {
            "status": expected_status(
                c20_complete, density_not_lower and irrelevant_median_ok and task_failure_ok
            ),
            "all_task_judgments_complete": judgments_complete,
            "density_not_lower": density_not_lower,
            "irrelevant_median_at_most_one": irrelevant_median_ok,
            "task_failure_increase_at_most_one": task_failure_ok,
        },
        "C21": {
            "status": expected_status(
                c21_complete,
                c21_complete and paired_raw["mean"] > 0 and paired_rate["mean"] > 0,
            ),
            "all_five_rates": paired_rate is not None and paired_rate["n"] == 5,
            "all_five_pairs_remove_catalog_rules": c21_has_contrast,
            "raw_higher": paired_raw is not None and paired_raw["n"] == 5
            and paired_raw["mean"] > 0,
            "rate_higher": paired_rate is not None and paired_rate["n"] == 5
            and paired_rate["mean"] > 0,
        },
        "C22": {
            "status": expected_status(
                c22_complete,
                c22_complete and treatment_listed["mean"] < control_listed["mean"],
            ),
            "all_five_rates": c22_complete,
            "treatment_rate_lower": c22_complete
            and treatment_listed["mean"] < control_listed["mean"],
        },
    }
    if row["claim_checks"] != expected_claims:
        raise ArtifactError("E-09 claim checks differ from run metrics")
    require_exact_keys(
        row["judge_agreement"],
        {"candidate_sets", "judged_sets", "agreement", "judge_error_blind_ids", "human_resolutions"},
        "E-09 judge agreement",
    )
    for field in ("candidate_sets", "judged_sets", "human_resolutions"):
        require_nonnegative_int(row["judge_agreement"][field], f"E-09 judge agreement {field}")
    require_number(row["judge_agreement"]["agreement"], "E-09 judge agreement", nullable=True)
    require_string_list(
        row["judge_agreement"]["judge_error_blind_ids"],
        "E-09 judge error blind ids",
        sorted_unique=True,
    )
    judge = row["judge_agreement"]
    if judge["judged_sets"] > judge["candidate_sets"] \
            or len(judge["judge_error_blind_ids"]) != judge["candidate_sets"] - judge["judged_sets"] \
            or judge["human_resolutions"] > judge["judged_sets"]:
        raise ArtifactError("E-09 judge agreement counts are impossible")
    expected_agreement = (
        (judge["judged_sets"] - judge["human_resolutions"]) / judge["judged_sets"]
        if judge["judged_sets"] else None
    )
    if judge["agreement"] != expected_agreement:
        raise ArtifactError("E-09 judge agreement differs from its counts")
    completed_at = row["completed_at"]
    require_canonical_utc(completed_at, "E-09 completed_at")
    if row["date"] != completed_at:
        raise ArtifactError("E-09 date differs from completed_at")
    payload = {key: value for key, value in row.items() if key not in ("run_id", "date")}
    if row["run_id"] != content_run_id(payload, completed_at):
        raise ArtifactError("E-09 run_id differs from its content")


EXPERIMENT_ROW_VALIDATORS = {"E-09": validate_e09_result_row}


def validate_compact_result_rows(lines, expected_lines, results_key: str):
    if sorted(map(canonical, lines)) != sorted(map(canonical, expected_lines)):
        raise ArtifactError(f"compact result lines differ from their complete ledger set: {results_key}")
    experiments = {line.get("experiment") for line in lines}
    if experiments == {"E-09"} and sorted(line.get("family") for line in lines) \
            != ["fable-subject", "kimi-subject"]:
        raise ArtifactError("E-09 compact result requires exactly one row per frozen model family")


def verify_ledger_references(
    repo_root: Path, expected_repository: str | None = None, verify_remote=False,
    baseline_ledger: Path | None = None, verified_manifest_list: Path | None = None,
):
    if verify_remote and expected_repository is None:
        raise ArtifactError("remote ledger verification requires expected_repository")
    ledger = repo_file(repo_root, "ledger/runs.jsonl")
    baseline_run_ids = set()
    if baseline_ledger is not None:
        require_regular_file(baseline_ledger, "baseline ledger")
        baseline = baseline_ledger.read_bytes()
        current = ledger.read_bytes()
        if not current.startswith(baseline):
            raise ArtifactError("ledger is not an append-only extension of the baseline")
        baseline_rows = load_jsonl(baseline_ledger)
        baseline_run_ids = {row.get("run_id") for row in baseline_rows}
        if any(not isinstance(run_id, str) or not run_id for run_id in baseline_run_ids) \
                or len(baseline_run_ids) != len(baseline_rows):
            raise ArtifactError("baseline ledger run_ids must be non-empty and unique")
    ledger_rows = load_jsonl(ledger)
    run_ids = [row.get("run_id") for row in ledger_rows]
    if any(not isinstance(run_id, str) or not run_id for run_id in run_ids) or len(run_ids) != len(set(run_ids)):
        raise ArtifactError("ledger run_ids must be non-empty and unique")
    checked = 0
    legacy_seen = set()
    legacy_cold_seen = set()
    remote_receipts = {}
    result_rows = {}
    ledger_result_rows = {}
    verified_manifests = set()
    for row in ledger_rows:
        legacy = LEGACY_ARTIFACTLESS_RUNS.get(row.get("run_id"))
        if legacy is not None:
            expected_experiment, expected_sha256 = legacy
            if row.get("experiment") != expected_experiment \
                    or sha256_bytes(canonical(row).encode()) != expected_sha256:
                raise ArtifactError(f"legacy artifactless row differs from its pin: {row.get('run_id')}")
            legacy_seen.add(row["run_id"])
        if "artifact" not in row:
            if legacy is not None:
                continue
            if row.get("type") == "experiment":
                if row.get("experiment") != "E-09-cold-reader":
                    raise ArtifactError(f"measured experiment row requires artifact evidence: {row.get('run_id')}")
                legacy_cold_sha256 = LEGACY_COLD_READER_RUNS.get(row.get("run_id"))
                if legacy_cold_sha256 is not None:
                    if row.get("tier") != "smoke" \
                            or sha256_bytes(canonical(row).encode()) != legacy_cold_sha256:
                        raise ArtifactError(f"legacy cold-reader row differs from its pin: {row.get('run_id')}")
                    legacy_cold_seen.add(row["run_id"])
                else:
                    validate_cold_reader_qualification_row(
                        row, repo_root,
                        require_current_inputs=baseline_ledger is not None
                        and row["run_id"] not in baseline_run_ids,
                    )
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
        if row.get("freeze_sha256") != manifest["freeze_sha256"]:
            raise ArtifactError(f"ledger freeze_sha256 differs from manifest: {row.get('run_id')}")
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
        validator = EXPERIMENT_ROW_VALIDATORS.get(row["experiment"])
        if validator is None:
            raise ArtifactError(f"numeric experiment has no trusted result-row validator: {row['experiment']}")
        validator(row, manifest)
        results_key = row["results_path"]
        if results_key not in result_rows:
            results_path = repo_file(repo_root, results_key)
            results = load_json(results_path)
            if not isinstance(results, dict) or set(results) != {"schema_version", "lines"} \
                    or results.get("schema_version") != 2 or not isinstance(results.get("lines"), list):
                raise ArtifactError(f"ledger results file is invalid: {row.get('run_id')}")
            lines = results["lines"]
            line_ids = [line.get("run_id") for line in lines if isinstance(line, dict)]
            if len(line_ids) != len(lines) or any(not isinstance(run_id, str) or not run_id for run_id in line_ids) \
                    or len(line_ids) != len(set(line_ids)):
                raise ArtifactError(f"ledger results lines require unique non-empty run_ids: {results_key}")
            result_rows[results_key] = lines
        ledger_result_rows.setdefault(results_key, []).append(row)
        verified_manifests.add(artifact["manifest_path"])
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
    if legacy_cold_seen != set(LEGACY_COLD_READER_RUNS):
        raise ArtifactError("ledger is missing pinned legacy cold-reader rows")
    for results_key, lines in result_rows.items():
        expected_lines = ledger_result_rows[results_key]
        validate_compact_result_rows(lines, expected_lines, results_key)
    if verified_manifest_list is not None:
        data = b"".join(path.encode() + b"\0" for path in sorted(verified_manifests))
        write_bytes_atomic(verified_manifest_list, data)
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
    ledger.add_argument("--verified-manifest-list", type=Path)
    membership = sub.add_parser("manifest-list-contains")
    membership.add_argument("--verified-manifest-list", type=Path, required=True)
    membership.add_argument("--path", required=True)
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
                verified_manifest_list=args.verified_manifest_list,
            )
        elif args.command == "manifest-list-contains":
            result = require_manifest_list_membership(args.verified_manifest_list, args.path)
        else:
            require_regular_file(args.manifest, "committed manifest")
            manifest = load_json(args.manifest)
            result = download_and_verify(manifest, args.manifest, args.expected_repository)
        print(json.dumps(result, sort_keys=True, indent=2))
    except ArtifactError as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
