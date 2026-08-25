#!/usr/bin/env python3
"""Build the artifact plan and synthetic raw root for the publication lifecycle proof.

The proof runs the packager and release commands end to end without measured
provider calls. It is not evidence: it creates no result and no ledger line.
Every field written here is revalidated by ``experiments/artifacts.py`` before
any archive, draft, or release exists.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


SMOKE = Path(__file__).resolve().parent
ROOT = SMOKE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import artifacts as artifact_store


EXPERIMENT = "artifact-storage-smoke"
INDEX = "experiments/artifact-storage-smoke/freeze.json"
POLICY = "experiments/artifact-storage-smoke/artifact-spec.json"
RECORD = "records/one.json"
CALL_MANIFEST = "record-manifest.jsonl"
RECORD_BYTES = b'{"kind":"synthetic","note":"lifecycle proof record","status":"ok"}\n'
CALL_MANIFEST_BYTES = b'{"event":"started","record":"records/one.json"}\n{"event":"completed","record":"records/one.json","status":"ok"}\n'


def frozen_bytes(commit: str, relative: str) -> bytes:
    return artifact_store.committed_file_bytes(ROOT, commit, relative)


def write_once(path: Path, data: bytes):
    """Never silently overwrite a staged record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise artifact_store.ArtifactError(f"staged record already differs: {path}")
        return
    path.write_bytes(data)


def build_plan(commit: str) -> dict:
    index_bytes = frozen_bytes(commit, INDEX)
    index = artifact_store.strict_json_loads(index_bytes)
    policy = artifact_store.strict_json_loads(frozen_bytes(commit, POLICY))
    batch_id = f"smoke-{commit[:12]}"
    return {
        "schema_version": artifact_store.SCHEMA_VERSION,
        "repository": policy["repository"],
        "experiment": EXPERIMENT,
        "batch_id": batch_id,
        "raw_root": f"experiments/artifact-storage-smoke/raw/measured/{batch_id}",
        "frozen_commit": commit,
        "freeze_sha256": artifact_store.sha256_bytes(index_bytes),
        "packager_commit": commit,
        "provenance": {**index["files"], INDEX: artifact_store.sha256_bytes(index_bytes)},
        "provenance_index": INDEX,
        "sanitization_policy_source": POLICY,
        "schedule": {
            "call_manifest_sha256": artifact_store.sha256_bytes(CALL_MANIFEST_BYTES),
            "record_sha256": artifact_store.sha256_bytes(RECORD_BYTES),
        },
        "expected_members": [
            {"path": CALL_MANIFEST, "kind": "call_manifest"},
            {"path": RECORD, "kind": "record"},
        ],
        "expected_counts": {"call_manifest": 1, "record": 1},
        "credential_env_names": policy["credential_env_names"],
        "forbidden_patterns": policy["forbidden_patterns"],
        "execution": {
            "call_manifest": {"started": 1, "completed": 1},
            "record_status_counts": {"ok": 1},
            "retry_attempts": 0,
            "exclusion_count": 0,
        },
        "exclusions": [],
        "release": {
            "tag": f"{EXPERIMENT}-{commit[:12]}",
            "archive_asset_name": f"{batch_id}{policy['archive_asset_suffix']}",
            "manifest_asset_name": f"{batch_id}{policy['manifest_asset_suffix']}",
        },
        "supersedes": None,
    }


def main() -> int:
    commit = artifact_store.run(["git", "rev-parse", "HEAD"], cwd=ROOT)
    artifact_store.require_commit(commit, "frozen_commit")
    plan = build_plan(commit)
    artifact_store.validate_plan(plan)

    raw_root = ROOT / plan["raw_root"]
    write_once(raw_root / RECORD, RECORD_BYTES)
    write_once(raw_root / CALL_MANIFEST, CALL_MANIFEST_BYTES)
    staged = {
        "call_manifest_sha256": artifact_store.sha256_file(raw_root / CALL_MANIFEST),
        "record_sha256": artifact_store.sha256_file(raw_root / RECORD),
    }
    if staged != plan["schedule"]:
        raise artifact_store.ArtifactError("staged raw records differ from the declared schedule")

    staging = SMOKE / ".artifacts"
    staging.mkdir(parents=True, exist_ok=True)
    plan_path = staging / f"{plan['batch_id']}.plan.json"
    write_once(plan_path, (artifact_store.canonical(plan) + "\n").encode())

    print(json.dumps({
        "batch_id": plan["batch_id"],
        "frozen_commit": commit,
        "plan": plan_path.relative_to(ROOT).as_posix(),
        "raw_root": plan["raw_root"],
        "tag": plan["release"]["tag"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except artifact_store.ArtifactError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
