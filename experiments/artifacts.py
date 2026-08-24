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
import os
import re
import stat
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


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


def load_json(path: Path):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"cannot read JSON: {path}") from exc


def write_json_exclusive(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise ArtifactError(f"refusing to overwrite: {path}") from exc
    try:
        data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def copy_exclusive(source: Path, target: Path):
    data = source.read_bytes()
    if target.exists():
        if target.read_bytes() != data:
            raise ArtifactError(f"committed manifest differs: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o644)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_dotenv(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
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
    if not raw_root.is_dir():
        raise ArtifactError(f"raw root is not a directory: {raw_root}")
    result = {}
    for directory, dirnames, filenames in os.walk(raw_root, followlinks=False):
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


def configured_secret_values(plan, repo_root: Path) -> list[bytes]:
    dotenv = read_dotenv(repo_root / ".env")
    names = set(plan.get("credential_env_names", []))
    names.update(name for name in dotenv if name.endswith(SECRET_SUFFIXES))
    names.update(name for name in os.environ if name.endswith(SECRET_SUFFIXES))
    values = set()
    for name in names:
        for value in (os.environ.get(name), dotenv.get(name)):
            if value and len(value) >= 8:
                values.add(value.encode())
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
        for secret in secret_values:
            if secret in data:
                raise ArtifactError(f"configured credential found in {relative}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactError(f"raw member is not UTF-8 text: {relative}") from exc
        try:
            if relative.endswith(".json"):
                json.loads(text)
            elif relative.endswith(".jsonl"):
                for number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        json.loads(line)
            else:
                raise ArtifactError(f"raw member must be JSON or JSONL: {relative}")
        except json.JSONDecodeError as exc:
            raise ArtifactError(f"raw member has invalid JSON: {relative}:{exc.lineno}") from exc
        for pattern_id, pattern in patterns:
            if pattern.search(text):
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
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(archive_path, flags, 0o644)
    except FileExistsError as exc:
        raise ArtifactError(f"refusing to overwrite: {archive_path}") from exc
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as raw_handle:
            descriptor = -1
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
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def validate_plan(plan):
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError(f"plan schema_version must be {SCHEMA_VERSION}")
    for field in (
        "repository", "experiment", "batch_id", "raw_root", "frozen_commit",
        "packager_commit", "schedule", "release",
    ):
        if not plan.get(field):
            raise ArtifactError(f"plan requires {field}")
    repository = plan["repository"]
    if not isinstance(repository.get("id"), int) or not repository.get("name"):
        raise ArtifactError("repository requires immutable numeric id and name")
    for field in ("tag", "archive_asset_name", "manifest_asset_name"):
        if not plan["release"].get(field):
            raise ArtifactError(f"release requires {field}")
    expected_map(plan)


def pack(plan, raw_root: Path, archive_path: Path, manifest_path: Path, repo_root: Path):
    validate_plan(plan)
    expected = expected_map(plan)
    actual = actual_regular_files(raw_root)
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing or unexpected:
        raise ArtifactError(f"inventory mismatch; missing={missing}, unexpected={unexpected}")
    scan, contents = scan_members(plan, actual, repo_root)
    members = sorted(expected)
    create_archive(contents, members, archive_path)
    member_rows = [{
        "bytes": len(contents[path]),
        "kind": expected[path],
        "path": path,
        "sha256": sha256_bytes(contents[path]),
    } for path in members]
    actual_counts = {}
    for row in member_rows:
        actual_counts[row["kind"]] = actual_counts.get(row["kind"], 0) + 1
    expected_counts = plan.get("expected_counts", {})
    if expected_counts and actual_counts != expected_counts:
        raise ArtifactError(f"kind counts differ; expected={expected_counts}, actual={actual_counts}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "repository": plan["repository"],
        "experiment": plan["experiment"],
        "batch_id": plan["batch_id"],
        "raw_root": plan["raw_root"],
        "frozen_commit": plan["frozen_commit"],
        "freeze_sha256": plan.get("freeze_sha256"),
        "packager_commit": plan["packager_commit"],
        "provenance": plan.get("provenance", {}),
        "schedule": plan["schedule"],
        "release": plan["release"],
        "supersedes": plan.get("supersedes"),
        "exclusions": plan.get("exclusions", []),
        "execution": plan.get("execution", {}),
        "inventory": {
            "expected_counts": expected_counts or actual_counts,
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
    write_json_exclusive(manifest_path, manifest)
    verify_local(manifest_path, archive_path)
    return manifest


def verify_local(manifest_path: Path, archive_path: Path):
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ArtifactError("unsupported manifest schema")
    archive_meta = manifest.get("archive", {})
    if archive_meta.get("sha256") != sha256_file(archive_path):
        raise ArtifactError("archive SHA-256 differs from manifest")
    if archive_meta.get("bytes") != archive_path.stat().st_size:
        raise ArtifactError("archive size differs from manifest")
    expected = {row["path"]: row for row in manifest.get("inventory", {}).get("members", [])}
    if not expected or len(expected) != len(manifest["inventory"]["members"]):
        raise ArtifactError("manifest member inventory is empty or duplicated")
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
                if (info.uid, info.gid, info.mode, int(info.mtime), info.uname, info.gname) != (0, 0, 0o644, 0, "", ""):
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
    manifest = load_json(manifest_path)
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
    return {asset["name"]: asset for asset in release.get("assets", [])}


def expected_server_digest(local_path: Path) -> str:
    return "sha256:" + sha256_file(local_path)


def release_by_tag_any_state(repo: str, tag: str, required=True):
    try:
        process = subprocess.run(
            ["gh", "release", "view", tag, "-R", repo, "--json", "databaseId"],
            text=True, capture_output=True, timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise ArtifactError(f"release lookup timed out: {tag}") from exc
    if process.returncode:
        if required:
            raise ArtifactError(process.stderr.strip() or f"release does not exist: {tag}")
        return None
    try:
        release_id = json.loads(process.stdout)["databaseId"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ArtifactError(f"cannot resolve release id for {tag}") from exc
    return gh_json(repo, f"releases/{release_id}")


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


def verify_superseded_release(manifest):
    old_tag = manifest.get("supersedes")
    if not old_tag:
        return
    if not isinstance(old_tag, str) or old_tag == manifest["release"]["tag"]:
        raise ArtifactError("supersedes must name a different release tag")
    old_release = gh_json(manifest["repository"]["name"], f"releases/tags/{old_tag}")
    if old_release.get("draft") or old_release.get("immutable") is not True:
        raise ArtifactError("supersedes must name a published immutable release")


def stage_release(manifest_path: Path, archive_path: Path):
    manifest = verify_local(manifest_path, archive_path)
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


def download_and_verify(manifest: dict, committed_manifest: Path | None = None):
    repo = manifest["repository"]["name"]
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


def publish_release(manifest_path: Path, archive_path: Path, confirm_tag: str, committed_copy: Path):
    manifest = verify_local(manifest_path, archive_path)
    repo = manifest["repository"]["name"]
    tag = manifest["release"]["tag"]
    if confirm_tag != tag:
        raise ArtifactError("--confirm-tag must exactly match the manifest tag")
    require_immutable_releases(repo)
    repository = verify_repository_identity(manifest)
    commit_is_on_default_branch(repo, manifest["frozen_commit"], repository)
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
    publish = sub.add_parser("publish-release")
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument("--archive", type=Path, required=True)
    publish.add_argument("--confirm-tag", required=True)
    publish.add_argument("--committed-copy", type=Path, required=True)
    remote = sub.add_parser("verify-release")
    remote.add_argument("--manifest", type=Path, required=True)
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
            result = stage_release(args.manifest, args.archive)
        elif args.command == "publish-release":
            result = publish_release(args.manifest, args.archive, args.confirm_tag, args.committed_copy)
        else:
            manifest = load_json(args.manifest)
            result = download_and_verify(manifest, args.manifest)
        print(json.dumps(result, sort_keys=True, indent=2))
    except ArtifactError as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
