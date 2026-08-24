#!/usr/bin/env python3

import io
import gzip
import json
import os
import statistics
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import artifacts as A


def plan():
    return {
        "schema_version": A.SCHEMA_VERSION,
        "repository": {"id": 1337622598, "name": "mlamp/meta-skills"},
        "experiment": "E-test",
        "batch_id": "m-test",
        "raw_root": "raw",
        "frozen_commit": "a" * 40,
        "freeze_sha256": "b" * 64,
        "packager_commit": "a" * 40,
        "provenance": {
            "artifact-spec.json": "e" * 64,
            "design.md": "c" * 64,
            "freeze.json": "b" * 64,
        },
        "provenance_index": "freeze.json",
        "sanitization_policy_source": "artifact-spec.json",
        "schedule": {"test_sha256": "d" * 64},
        "expected_members": [
            {"path": "interviews/one.json", "kind": "interview"},
            {"path": "record-manifest.jsonl", "kind": "call_manifest"},
        ],
        "expected_counts": {"call_manifest": 1, "interview": 1},
        "credential_env_names": ["TEST_ARTIFACT_API_KEY"],
        "forbidden_patterns": [{"id": "private", "regex": "PRIVATE-MARKER"}],
        "execution": {
            "call_manifest": {"started": 1, "completed": 1},
            "record_status_counts": {"ok": 1},
            "retry_attempts": 0,
            "exclusion_count": 0,
        },
        "exclusions": [],
        "release": {
            "tag": "evidence-test-m-test",
            "archive_asset_name": "m-test.raw.tar.gz",
            "manifest_asset_name": "m-test.manifest.json",
        },
        "supersedes": None,
    }


def pinned_legacy_rows():
    ledger = Path(__file__).resolve().parent.parent / "ledger" / "runs.jsonl"
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    pinned = set(A.LEGACY_ARTIFACTLESS_RUNS) | set(A.LEGACY_COLD_READER_RUNS)
    return [row for row in rows if row.get("run_id") in pinned]


def retarget_manifest_experiment(payload, experiment):
    directory = experiment.lower().replace("-", "")
    provenance = dict(payload["provenance"])
    provenance[f"experiments/{directory}/freeze.json"] = provenance.pop("freeze.json")
    provenance[f"experiments/{directory}/artifact-spec.json"] = provenance.pop("artifact-spec.json")
    payload.update({
        "experiment": experiment,
        "provenance": provenance,
        "provenance_index": f"experiments/{directory}/freeze.json",
        "sanitization_policy_source": f"experiments/{directory}/artifact-spec.json",
    })


def write_test_ledger(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(A.canonical(row) + "\n" for row in [*pinned_legacy_rows(), *rows]), encoding="utf-8")


def e09_stats(values=None):
    values = [0, 0, 0, 0, 0] if values is None else values
    return {
        "n": len(values),
        "values": values,
        "mean": statistics.mean(values),
        "sample_variance": statistics.variance(values) if len(values) > 1 else 0,
        "sample_stdev": statistics.stdev(values) if len(values) > 1 else 0,
    }


def e09_condition():
    return {
        "task_successes": 0,
        "task_failures": 4,
        "task_judge_errors": 0,
        "listed_hits": 0,
        "output_tokens": 0,
        "listed_rate_per_1000": None,
        "substitute_hits": 0,
        "substitute_rate_per_1000": None,
        "substitute_buckets": {"unaided_only": 0, "catalog_mapped_only": 0, "both": 0},
        "outside_selected_substitute_candidates": 0,
        "substitute_judgment_complete": True,
    }


def e09_arm(treatment=False):
    runs = []
    for rep in range(1, 6):
        conditions = {"suppression": e09_condition()}
        if treatment:
            conditions["no_suppression"] = e09_condition()
        runs.append({
            "rep": rep,
            "selected_ids": [],
            "automatic_bans": [],
            "selected_relevant": 0,
            "coverage": 0,
            "selection_precision": 1,
            "irrelevant_selections": 0,
            "contract_tokens": 0,
            "over_cap": False,
            "contract_violations": [],
            "interview_status": "ok",
            "rendered_relevant": 0,
            "coverage_per_100_contract_tokens": 0,
            "catalog_rules_removed_in_no_suppression": 0,
            "catalog_rule_tokens_removed_in_no_suppression": 0,
            "conditions": conditions,
        })
    summary = {
        "task_failures": e09_stats([4, 4, 4, 4, 4]),
        "listed_hits": e09_stats(),
        "listed_rate_per_1000": None,
        "listed_pooled": {"hits": 0, "tokens": 0, "rate_per_1000": None},
        "substitute_hits": e09_stats(),
        "substitute_rate_per_1000": None,
        "substitute_pooled": {"hits": 0, "tokens": 0, "rate_per_1000": None},
    }
    return {
        "runs": runs,
        "selected_relevant": e09_stats(),
        "coverage": e09_stats(),
        "selection_precision": e09_stats([1, 1, 1, 1, 1]),
        "irrelevant_selections": e09_stats(),
        "irrelevant_selection_median": 0,
        "contract_tokens": e09_stats(),
        "coverage_per_100_contract_tokens": e09_stats(),
        "suppression": summary,
        "no_suppression": summary if treatment else None,
        "substitute_paired_raw_difference": e09_stats() if treatment else None,
        "substitute_paired_rate_difference": None,
        "over_cap_count": 0,
        "contract_violation_count": 0,
        "interview_error_count": 0,
    }


def e09_result_row():
    completed_at = "2026-08-24T00:00:00+00:00"
    row = {
        "run_id": "pending",
        "date": completed_at,
        "schema_version": 2,
        "type": "experiment",
        "experiment": "E-09",
        "batch_id": "m-test",
        "family": "fable-subject",
        "arms": {"control": e09_arm(), "treatment": e09_arm(treatment=True)},
        "claim_checks": {
            "C19": {"status": "fail", "mean_gain": 0, "ceiling_blocks_one_pattern_gain": False,
                    "passes_screen": False},
            "C20": {"status": "pass", "all_task_judgments_complete": True,
                    "density_not_lower": True, "irrelevant_median_at_most_one": True,
                    "task_failure_increase_at_most_one": True},
            "C21": {"status": "incomplete", "all_five_rates": False,
                    "all_five_pairs_remove_catalog_rules": False, "raw_higher": False,
                    "rate_higher": False},
            "C22": {"status": "incomplete", "all_five_rates": False,
                    "treatment_rate_lower": False},
        },
        "judge_agreement": {"candidate_sets": 0, "judged_sets": 0, "agreement": None,
                            "judge_error_blind_ids": [], "human_resolutions": 0},
        "reps_per_arm": 5,
        "sample_variance": "n-1",
        "seed": 20260821,
        "judge_seed": 20260822,
        "artifact": {},
        "results_path": "experiments/e09/results/m-test.json",
        "freeze_sha256": "a" * 64,
        "completed_at": completed_at,
    }
    payload = {key: value for key, value in row.items() if key not in ("run_id", "date")}
    row["run_id"] = A.content_run_id(payload, completed_at)
    return row


def e09_manifest():
    return {"experiment": "E-09", "batch_id": "m-test", "freeze_sha256": "a" * 64}


class ArtifactPackTest(unittest.TestCase):
    def make_raw(self, root):
        raw = root / "raw"
        (raw / "interviews").mkdir(parents=True)
        (raw / "interviews" / "one.json").write_text('{"ok":true}\n', encoding="utf-8")
        (raw / "record-manifest.jsonl").write_text('{"event":"completed"}\n', encoding="utf-8")
        return raw

    def pack_at(self, root, suffix):
        raw = self.make_raw(root) if not (root / "raw").exists() else root / "raw"
        archive = root / f"bundle-{suffix}.tar.gz"
        manifest = root / f"manifest-{suffix}.json"
        A.pack(plan(), raw, archive, manifest, root)
        return archive, manifest

    def test_pack_is_byte_deterministic_and_self_verifying(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            first_archive, first_manifest = self.pack_at(root, "one")
            second_archive, second_manifest = self.pack_at(root, "two")
            self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
            self.assertEqual(first_manifest.read_bytes(), second_manifest.read_bytes())
            manifest = A.verify_local(first_manifest, first_archive)
            self.assertEqual([row["path"] for row in manifest["inventory"]["members"]],
                             ["interviews/one.json", "record-manifest.jsonl"])
            self.assertEqual(A.verify_source(first_manifest, plan(), root / "raw", root), manifest)

    def test_source_verifier_rejects_post_pack_raw_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, manifest = self.pack_at(root, "one")
            (root / "raw" / "interviews" / "one.json").write_text('{"ok":false}\n', encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "differs"):
                A.verify_source(manifest, plan(), root / "raw", root)

    def test_missing_unexpected_and_symlink_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            (raw / "extra.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "inventory mismatch"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            (raw / "interviews" / "one.json").unlink()
            os.symlink(raw / "record-manifest.jsonl", raw / "interviews" / "one.json")
            with self.assertRaisesRegex(A.ArtifactError, "symlink"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)

    def test_path_traversal_in_expected_inventory_is_rejected(self):
        for path in ("../secret.json", r"..\secret.json", "C:/secret.json"):
            bad = plan()
            bad["expected_members"] = [{"path": path, "kind": "raw"}]
            with self.assertRaisesRegex(A.ArtifactError, "unsafe"):
                A.validate_plan(bad)

    def test_schema_version_and_release_names_are_strict(self):
        self.assertEqual(A.SCHEMA_VERSION, 2)
        for asset in ("nested/archive.tar.gz", "-archive.tar.gz"):
            bad = plan()
            bad["release"]["archive_asset_name"] = asset
            with self.assertRaises(A.ArtifactError):
                A.validate_plan(bad)
        bad = plan()
        bad["release"]["manifest_asset_name"] = bad["release"]["archive_asset_name"]
        with self.assertRaisesRegex(A.ArtifactError, "must differ"):
            A.validate_plan(bad)

    def test_exact_secret_and_frozen_patterns_are_rejected_without_echoing_secret(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            secret = "never-print-this-secret"
            (root / ".env").write_text(f"TEST_ARTIFACT_API_KEY={secret}\n", encoding="utf-8")
            (raw / "interviews" / "one.json").write_text(json.dumps({"value": secret}), encoding="utf-8")
            with self.assertRaises(A.ArtifactError) as caught:
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)
            self.assertNotIn(secret, str(caught.exception))
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            (raw / "interviews" / "one.json").write_text('{"value":"PRIVATE-MARKER"}', encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "sanitization pattern private"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)

    def test_short_exported_secret_and_decoded_windows_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            secret = "abc1234"
            (root / ".env").write_text(f"export TEST_ARTIFACT_API_KEY={secret}\n", encoding="utf-8")
            (raw / "interviews" / "one.json").write_text(json.dumps({"value": secret}), encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "configured credential"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            windows_plan = plan()
            windows_plan["forbidden_patterns"].append({
                "id": "windows", "regex": r"[A-Za-z]:\\Users\\[^\\]+",
            })
            (raw / "interviews" / "one.json").write_text(
                json.dumps({"path": r"C:\Users\alice"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(A.ArtifactError, "sanitization pattern windows"):
                A.pack(windows_plan, raw, root / "a.tar.gz", root / "a.json", root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            windows_plan = plan()
            windows_plan["forbidden_patterns"].append({
                "id": "windows", "regex": r"[A-Za-z]:\\Users\\[^\\]+",
            })
            nested = json.dumps({"path": r"C:\Users\alice"})
            (raw / "interviews" / "one.json").write_text(json.dumps({"event": nested}), encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "sanitization pattern windows"):
                A.pack(windows_plan, raw, root / "a.tar.gz", root / "a.json", root)

    def test_every_nested_json_string_is_scanned_and_resource_overflow_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            secret = "nested-secret"
            (root / ".env").write_text(f"TEST_ARTIFACT_API_KEY={secret}\n", encoding="utf-8")
            nested = secret
            for _ in range(12):
                nested = json.dumps(nested)
            (raw / "interviews" / "one.json").write_text(json.dumps({"event": nested}), encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "configured credential"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)
        with mock.patch.object(A, "MAX_DECODED_STRINGS", 1):
            with self.assertRaisesRegex(A.ArtifactError, "resource limit"):
                list(A.json_strings(["one", "two"]))

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers_at_every_depth(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"value":"first","value":"second"}\n', encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "duplicate JSON object key"):
                A.load_json(duplicate)
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"value":NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "non-finite JSON number"):
                A.load_json(nonfinite)
            overflow = root / "overflow.json"
            overflow.write_text('{"value":1e999}\n', encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "non-finite JSON number"):
                A.load_json(overflow)
        with self.assertRaisesRegex(A.ArtifactError, "duplicate JSON object key"):
            list(A.json_strings({"nested": '{"value":1,"value":2}'}))
        with self.assertRaisesRegex(A.ArtifactError, "non-finite JSON number"):
            list(A.json_strings({"nested": '{"value":Infinity}'}))
        with self.assertRaisesRegex(A.ArtifactError, "non-finite JSON number"):
            list(A.json_strings({"nested": '{"value":-1e999}'}))

    def test_duplicate_key_cannot_hide_an_escaped_secret(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            secret = "hidden-secret"
            (root / ".env").write_text(f"TEST_ARTIFACT_API_KEY={secret}\n", encoding="utf-8")
            escaped = "".join(f"\\u{ord(character):04x}" for character in secret)
            (raw / "interviews" / "one.json").write_text(
                f'{{"value":"{escaped}","value":"safe"}}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(A.ArtifactError, "duplicate JSON object key"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)

    def test_source_rebind_pins_complete_sanitization_policy(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, manifest = self.pack_at(root, "one")
            changed = plan()
            changed["forbidden_patterns"][0]["regex"] = "(?!)"
            with self.assertRaisesRegex(A.ArtifactError, "sanitization result differs"):
                A.verify_source(manifest, changed, root / "raw", root)

    def test_manifest_requires_explicit_supersedes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            payload = A.load_json(manifest)
            payload.pop("supersedes")
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "requires supersedes"):
                A.verify_local(manifest, archive)

    def test_repository_boolean_is_not_a_numeric_identity(self):
        bad = plan()
        bad["repository"]["id"] = True
        with self.assertRaisesRegex(A.ArtifactError, "positive immutable numeric id"):
            A.validate_plan(bad)

    def test_raw_root_must_match_plan_and_must_not_be_a_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            bad = plan()
            bad["raw_root"] = "elsewhere"
            with self.assertRaisesRegex(A.ArtifactError, "raw root differs"):
                A.pack(bad, raw, root / "a.tar.gz", root / "a.json", root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            real = root / "real"
            (real / "interviews").mkdir(parents=True)
            (real / "interviews" / "one.json").write_text("{}\n", encoding="utf-8")
            (real / "record-manifest.jsonl").write_text("{}\n", encoding="utf-8")
            os.symlink(real, root / "raw")
            with self.assertRaisesRegex(A.ArtifactError, "symlink"):
                A.pack(plan(), root / "raw", root / "a.tar.gz", root / "a.json", root)

    def test_walk_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)

            def fail_walk(*args, **kwargs):
                kwargs["onerror"](PermissionError(13, "denied", str(raw / "closed")))
                return []

            with mock.patch.object(A.os, "walk", side_effect=fail_walk):
                with self.assertRaisesRegex(A.ArtifactError, "cannot traverse"):
                    A.actual_regular_files(raw)

    def test_interrupted_archive_leaves_no_final_and_incomplete_pair_recovers(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive = root / "broken.tar.gz"
            with mock.patch.object(A.tarfile, "open", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    A.create_archive({"one.json": b"{}"}, ["one.json"], archive)
            self.assertFalse(archive.exists())
            self.assertEqual(list(root.glob(".*.tmp")), [])
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            archive_bytes = archive.read_bytes()
            manifest.unlink()
            A.pack(plan(), root / "raw", archive, manifest, root)
            self.assertEqual(archive.read_bytes(), archive_bytes)
            A.verify_local(manifest, archive)

    def test_plan_requires_freeze_provenance_and_exact_counts(self):
        for field in ("freeze_sha256", "provenance", "provenance_index", "sanitization_policy_source"):
            bad = plan()
            bad.pop(field)
            with self.assertRaisesRegex(A.ArtifactError, f"requires {field}"):
                A.validate_plan(bad)
        bad = plan()
        bad["expected_counts"] = {"interview": 2}
        with self.assertRaisesRegex(A.ArtifactError, "expected_counts"):
            A.validate_plan(bad)
        bad = plan()
        bad["experiment"] = "E-09"
        with self.assertRaisesRegex(A.ArtifactError, "noncanonical frozen source paths"):
            A.validate_plan(bad)

    def test_local_verifier_rejects_archive_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(A.ArtifactError, "SHA-256"):
                A.verify_local(manifest, archive)

    def test_invalid_json_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            raw = self.make_raw(root)
            (raw / "interviews" / "one.json").write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "invalid JSON"):
                A.pack(plan(), raw, root / "a.tar.gz", root / "a.json", root)

    def test_local_verifier_rejects_unsafe_archive_member(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            with archive.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
                    with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as handle:
                        info = tarfile.TarInfo("../escape.json")
                        info.size = 2
                        info.mode = 0o644
                        info.uid = info.gid = info.mtime = 0
                        info.uname = info.gname = ""
                        handle.addfile(info, io.BytesIO(b"{}"))
            payload = A.load_json(manifest)
            payload["archive"]["sha256"] = A.sha256_file(archive)
            payload["archive"]["bytes"] = archive.stat().st_size
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "unsafe"):
                A.verify_local(manifest, archive)

    def test_local_verifier_recomputes_counts_and_rejects_fractional_mtime(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            payload = A.load_json(manifest)
            payload["inventory"]["expected_counts"]["interview"] = 2
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "counts differ"):
                A.verify_local(manifest, archive)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            payload = A.load_json(manifest)
            contents = {
                row["path"]: (root / "raw" / row["path"]).read_bytes()
                for row in payload["inventory"]["members"]
            }
            with archive.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
                    with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                        for index, relative in enumerate(sorted(contents)):
                            info = tarfile.TarInfo(relative)
                            info.size = len(contents[relative])
                            info.mtime = 0.5 if index == 0 else 0
                            info.mode = 0o644
                            info.uid = info.gid = 0
                            info.uname = info.gname = ""
                            bundle.addfile(info, io.BytesIO(contents[relative]))
            payload["archive"]["sha256"] = A.sha256_file(archive)
            payload["archive"]["bytes"] = archive.stat().st_size
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "metadata is not normalized"):
                A.verify_local(manifest, archive)

    def test_local_verifier_rejects_wrong_gzip_header_and_member_order(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("interviews/one.json")
                info.size = 2
                bundle.addfile(info, io.BytesIO(b"{}"))
            payload = A.load_json(manifest)
            payload["archive"].update({"sha256": A.sha256_file(archive), "bytes": archive.stat().st_size})
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "gzip header"):
                A.verify_local(manifest, archive)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest = self.pack_at(root, "one")
            payload = A.load_json(manifest)
            contents = {row["path"]: (root / "raw" / row["path"]).read_bytes()
                        for row in payload["inventory"]["members"]}
            with archive.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as zipped:
                    with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                        for relative in reversed(sorted(contents)):
                            info = tarfile.TarInfo(relative)
                            info.size = len(contents[relative])
                            info.mode = 0o644
                            info.uid = info.gid = info.mtime = 0
                            info.uname = info.gname = ""
                            bundle.addfile(info, io.BytesIO(contents[relative]))
            payload["archive"].update({"sha256": A.sha256_file(archive), "bytes": archive.stat().st_size})
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "member order"):
                A.verify_local(manifest, archive)


class ReleaseGateTest(unittest.TestCase):
    def packed(self, root):
        return ArtifactPackTest().pack_at(root, "release")

    def release(self, manifest_path, archive, **overrides):
        manifest = A.load_json(manifest_path)
        value = {
            "id": 42,
            "draft": True,
            "immutable": False,
            "target_commitish": manifest["frozen_commit"],
            "assets": [{
                "name": manifest["release"]["archive_asset_name"],
                "size": archive.stat().st_size,
                "digest": "sha256:" + A.sha256_file(archive),
            }, {
                "name": manifest["release"]["manifest_asset_name"],
                "size": manifest_path.stat().st_size,
                "digest": "sha256:" + A.sha256_file(manifest_path),
            }],
        }
        value.update(overrides)
        return value

    def test_immutable_setting_is_required(self):
        with mock.patch.object(A, "gh_json", return_value={"enabled": False}):
            with self.assertRaisesRegex(A.ArtifactError, "not enabled"):
                A.require_immutable_releases("owner/repo")

    def test_release_commands_require_local_frozen_head(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with mock.patch.object(A, "run", return_value="b" * 40):
                with self.assertRaisesRegex(A.ArtifactError, "local HEAD"):
                    A.require_local_frozen_source(root, {
                        "frozen_commit": "a" * 40, "provenance": {"design.md": "b" * 64},
                    })

    def test_release_commands_reject_uncommitted_packager_or_provenance_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            packager = root / "experiments" / "artifacts.py"
            packager.parent.mkdir(parents=True)
            packager_bytes = b"frozen packager\n"
            packager.write_bytes(packager_bytes)
            design = root / "design.md"
            design.write_text("locally changed\n", encoding="utf-8")
            spec_bytes = json.dumps({
                "credential_env_names": ["TEST_ARTIFACT_API_KEY"],
                "forbidden_patterns": [{"id": "private", "regex": "PRIVATE-MARKER"}],
            }).encode()
            (root / "artifact-spec.json").write_bytes(spec_bytes)
            frozen_files = {
                "artifact-spec.json": A.sha256_bytes(spec_bytes),
                "design.md": A.sha256_bytes(b"frozen design\n"),
                "experiments/artifacts.py": A.sha256_bytes(packager_bytes),
            }
            freeze_bytes = json.dumps({"files": frozen_files}).encode()
            (root / "freeze.json").write_bytes(freeze_bytes)
            policy = {
                "credential_env_names": ["TEST_ARTIFACT_API_KEY"],
                "forbidden_patterns": [{"id": "private", "regex": "PRIVATE-MARKER"}],
            }
            manifest = {
                "frozen_commit": "a" * 40,
                "freeze_sha256": A.sha256_bytes(freeze_bytes),
                "provenance": {**frozen_files, "freeze.json": A.sha256_bytes(freeze_bytes)},
                "provenance_index": "freeze.json",
                "sanitization_policy_source": "artifact-spec.json",
                "sanitization": {"policy_sha256": A.sha256_bytes(A.canonical(policy).encode())},
            }
            committed = {**{
                "artifact-spec.json": spec_bytes,
                "design.md": b"frozen design\n",
                "experiments/artifacts.py": packager_bytes,
            }, "freeze.json": freeze_bytes}
            with mock.patch.object(A, "__file__", str(packager)), \
                 mock.patch.object(A, "run", return_value="a" * 40), \
                 mock.patch.object(A, "committed_file_bytes", side_effect=lambda root, commit, path: committed[path]):
                with self.assertRaisesRegex(A.ArtifactError, "working file differs"):
                    A.require_local_frozen_source(root, manifest)

    def test_release_commands_bind_policy_and_provenance_to_frozen_index(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            packager = root / "experiments" / "artifacts.py"
            packager.parent.mkdir(parents=True)
            packager_bytes = b"frozen packager\n"
            packager.write_bytes(packager_bytes)
            policy = {
                "credential_env_names": ["TEST_ARTIFACT_API_KEY"],
                "forbidden_patterns": [{"id": "private", "regex": "PRIVATE-MARKER"}],
            }
            spec_bytes = json.dumps(policy).encode()
            (root / "artifact-spec.json").write_bytes(spec_bytes)
            frozen_files = {
                "artifact-spec.json": A.sha256_bytes(spec_bytes),
                "experiments/artifacts.py": A.sha256_bytes(packager_bytes),
            }
            freeze_bytes = json.dumps({"files": frozen_files}).encode()
            (root / "freeze.json").write_bytes(freeze_bytes)
            weakened = {"credential_env_names": ["TEST_ARTIFACT_API_KEY"], "forbidden_patterns": []}
            manifest = {
                "frozen_commit": "a" * 40,
                "freeze_sha256": A.sha256_bytes(freeze_bytes),
                "provenance": {**frozen_files, "freeze.json": A.sha256_bytes(freeze_bytes)},
                "provenance_index": "freeze.json",
                "sanitization_policy_source": "artifact-spec.json",
                "sanitization": {"policy_sha256": A.sha256_bytes(A.canonical(weakened).encode())},
            }
            committed = {
                "artifact-spec.json": spec_bytes,
                "experiments/artifacts.py": packager_bytes,
                "freeze.json": freeze_bytes,
            }
            with mock.patch.object(A, "__file__", str(packager)), \
                 mock.patch.object(A, "run", return_value="a" * 40), \
                 mock.patch.object(A, "committed_file_bytes", side_effect=lambda root, commit, path: committed[path]):
                with self.assertRaisesRegex(A.ArtifactError, "sanitizer policy differs"):
                    A.require_local_frozen_source(root, manifest)
            missing = {**manifest, "provenance": {"freeze.json": A.sha256_bytes(freeze_bytes)}}
            with mock.patch.object(A, "__file__", str(packager)), \
                 mock.patch.object(A, "run", return_value="a" * 40), \
                 mock.patch.object(A, "committed_file_bytes", side_effect=lambda root, commit, path: committed[path]):
                with self.assertRaisesRegex(A.ArtifactError, "provenance differs"):
                    A.require_local_frozen_source(root, missing)

    def test_server_assets_require_exact_names_sizes_and_digests(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = ArtifactPackTest().pack_at(root, "one")
            manifest = A.load_json(manifest_path)
            release = {"assets": [{
                "name": manifest["release"]["archive_asset_name"],
                "size": archive.stat().st_size,
                "digest": "sha256:" + A.sha256_file(archive),
            }, {
                "name": manifest["release"]["manifest_asset_name"],
                "size": manifest_path.stat().st_size,
                "digest": "sha256:" + A.sha256_file(manifest_path),
            }]}
            A.verify_server_assets(release, manifest_path, archive)
            release["assets"][0]["digest"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(A.ArtifactError, "server digest differs"):
                A.verify_server_assets(release, manifest_path, archive)

    def test_supersedes_must_name_a_different_published_immutable_release(self):
        manifest = plan()
        manifest["supersedes"] = manifest["release"]["tag"]
        with self.assertRaisesRegex(A.ArtifactError, "different release tag"):
            A.verify_superseded_release(manifest)
        manifest["supersedes"] = "older-tag"
        with mock.patch.object(A, "gh_json", return_value={"draft": True, "immutable": False}):
            with self.assertRaisesRegex(A.ArtifactError, "published immutable"):
                A.verify_superseded_release(manifest)

    def test_draft_lookup_uses_fail_closed_release_listing(self):
        with mock.patch.object(A, "gh_paginated_json", return_value=[
            {"id": 42, "tag_name": "tag", "draft": True}
        ]) as listing:
            self.assertEqual(A.release_by_tag_any_state("owner/repo", "tag"), {
                "id": 42, "tag_name": "tag", "draft": True,
            })
        listing.assert_called_once_with("owner/repo", "releases?per_page=100")
        with mock.patch.object(A, "gh_paginated_json", side_effect=A.ArtifactError("network")):
            with self.assertRaisesRegex(A.ArtifactError, "network"):
                A.release_by_tag_any_state("owner/repo", "missing", required=False)
        with mock.patch.object(A, "gh_paginated_json", return_value=[
            {"id": 42, "tag_name": "tag"}, {"id": 43, "tag_name": "tag"},
        ]):
            with self.assertRaisesRegex(A.ArtifactError, "multiple releases"):
                A.release_by_tag_any_state("owner/repo", "tag")

    def test_existing_tag_lookup_is_paginated_and_exact(self):
        refs = [
            {"ref": "refs/tags/tag-extra", "object": {"type": "commit", "sha": "b" * 40}},
            {"ref": "refs/tags/tag", "object": {"type": "commit", "sha": "a" * 40}},
        ]
        with mock.patch.object(A, "gh_paginated_json", return_value=refs) as listing:
            self.assertEqual(A.existing_tag_commit("owner/repo", "tag"), "a" * 40)
        listing.assert_called_once_with("owner/repo", "git/matching-refs/tags/tag?per_page=100")

    def test_stage_resume_reuploads_exact_draft_assets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            release = self.release(manifest_path, archive)
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "require_local_frozen_source"), \
                 mock.patch.object(A, "verify_repository_identity", return_value={"default_branch": "main"}), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "verify_superseded_release"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "wait_for_server_assets", return_value=release), \
                 mock.patch.object(A, "run", return_value="") as runner:
                receipt = A.stage_release(manifest_path, archive, plan(), root / "raw", root)
            self.assertEqual(receipt, {"release_id": 42, "state": "draft", "tag": "evidence-test-m-test"})
            command = runner.call_args.args[0]
            self.assertEqual(command[:4], ["gh", "release", "upload", "evidence-test-m-test"])
            self.assertIn("--clobber", command)

    def test_release_commands_recheck_pack_plan_and_raw_source(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            payload = A.load_json(manifest_path)
            payload["exclusions"] = [{"path": "interviews/one.json", "reason": "edited"}]
            payload["execution"]["exclusion_count"] = 1
            manifest_path.unlink()
            A.write_json_exclusive(manifest_path, payload)
            with mock.patch.object(A, "require_local_frozen_source"), \
                 self.assertRaisesRegex(A.ArtifactError, "current plan: exclusions"):
                A.stage_release(manifest_path, archive, plan(), root / "raw", root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            (root / "raw" / "interviews" / "one.json").write_text('{"changed":true}\n', encoding="utf-8")
            with mock.patch.object(A, "require_local_frozen_source"), \
                 self.assertRaisesRegex(A.ArtifactError, "differs"):
                A.stage_release(manifest_path, archive, plan(), root / "raw", root)

    def test_numeric_release_plan_is_rederived_by_its_frozen_harness(self):
        value = plan()
        retarget_manifest_experiment(value, "E-09")
        with mock.patch.object(A, "repo_file", return_value=Path("/repo/experiments/e09/harness.py")), \
             mock.patch.object(A, "run", return_value=A.canonical(value)) as runner:
            A.verify_trusted_plan(value, Path("/repo"))
        runner.assert_called_once_with([
            A.sys.executable, "/repo/experiments/e09/harness.py", "artifact-plan-json",
        ], cwd=Path("/repo"), timeout=300)
        changed = json.loads(json.dumps(value))
        changed["execution"]["retry_attempts"] = 1
        with mock.patch.object(A, "repo_file", return_value=Path("/repo/experiments/e09/harness.py")), \
             mock.patch.object(A, "run", return_value=A.canonical(value)), \
             self.assertRaisesRegex(A.ArtifactError, "differs from the frozen harness"):
            A.verify_trusted_plan(changed, Path("/repo"))
        disguised = {**value, "experiment": "artifact-storage-smoke"}
        with self.assertRaisesRegex(A.ArtifactError, "wrong experiment id"):
            A.verify_trusted_plan(disguised, Path("/repo"))

    def test_remote_verifier_binds_expected_repository_before_network(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, manifest_path = self.packed(root)
            with mock.patch.object(A, "gh_json") as github:
                with self.assertRaisesRegex(A.ArtifactError, "verifier repository"):
                    A.download_and_verify(
                        A.load_json(manifest_path), manifest_path, expected_repository="other/repo"
                    )
            github.assert_not_called()

    def test_remote_verifier_rejects_nonregular_committed_manifest_before_network(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            target = root / "target.json"
            target.write_text("{}\n", encoding="utf-8")
            linked = root / "manifest.json"
            os.symlink(target, linked)
            with mock.patch.object(A, "verify_repository_identity") as remote:
                with self.assertRaisesRegex(A.ArtifactError, "not an unlinked regular file"):
                    A.download_and_verify(plan(), linked)
            remote.assert_not_called()

    def test_remote_verifier_requires_frozen_commit_on_default_branch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, manifest_path = self.packed(root)
            manifest = A.load_json(manifest_path)
            with mock.patch.object(A, "verify_repository_identity", return_value={"default_branch": "main"}), \
                 mock.patch.object(A, "commit_is_on_default_branch", side_effect=A.ArtifactError("not contained")):
                with self.assertRaisesRegex(A.ArtifactError, "not contained"):
                    A.download_and_verify(manifest, manifest_path)

    def test_publish_checks_existing_tag_and_committed_copy_before_irreversible_edit(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            committed = root / "tracked" / "manifest.json"
            release = self.release(manifest_path, archive)
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "require_local_frozen_source"), \
                 mock.patch.object(A, "verify_repository_identity", return_value={"default_branch": "main"}), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "verify_superseded_release"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "existing_tag_commit", return_value="b" * 40), \
                 mock.patch.object(A, "run") as runner:
                with self.assertRaisesRegex(A.ArtifactError, "tag points to the wrong commit"):
                    A.publish_release(
                        manifest_path, archive, "evidence-test-m-test", committed,
                        plan(), root / "raw", root,
                    )
            runner.assert_not_called()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            committed = root / "tracked" / "manifest.json"
            committed.parent.mkdir(parents=True)
            committed.write_text("conflict\n", encoding="utf-8")
            with mock.patch.object(A, "require_local_frozen_source"), \
                 mock.patch.object(A, "require_immutable_releases") as immutable:
                with self.assertRaisesRegex(A.ArtifactError, "committed manifest differs"):
                    A.publish_release(
                        manifest_path, archive, "evidence-test-m-test", committed,
                        plan(), root / "raw", root,
                    )
            immutable.assert_not_called()

    def test_committed_copy_rejects_redirected_parent_before_creation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source = root / "manifest.json"
            source.write_text("{}\n", encoding="utf-8")
            actual = root / "actual"
            actual.mkdir()
            (root / "redirected").symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(A.ArtifactError, "contains a symlink"):
                A.preflight_committed_copy(source, root / "redirected" / "copy.json", root)
            self.assertFalse((actual / "copy.json").exists())

    def test_publish_retry_accepts_matching_immutable_release_and_copies_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            committed = root / "tracked" / "manifest.json"
            release = self.release(manifest_path, archive, draft=False, immutable=True)
            receipt = {"verified": True, "release_id": 42}
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "require_local_frozen_source"), \
                 mock.patch.object(A, "verify_repository_identity"), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "gh_json", return_value=release), \
                 mock.patch.object(A, "download_and_verify", return_value=receipt) as download, \
                 mock.patch.object(A, "run") as runner:
                self.assertEqual(A.publish_release(
                    manifest_path, archive, "evidence-test-m-test", committed,
                    plan(), root / "raw", root,
                ), receipt)
            runner.assert_not_called()
            download.assert_called_once_with(A.load_json(manifest_path), manifest_path)
            self.assertEqual(committed.read_bytes(), manifest_path.read_bytes())

    def test_publish_retry_recovers_after_post_publish_verification_failure(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            committed = root / "tracked" / "manifest.json"
            release = self.release(manifest_path, archive, draft=False, immutable=True)
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "require_local_frozen_source"), \
                 mock.patch.object(A, "verify_repository_identity"), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "gh_json", return_value=release), \
                 mock.patch.object(A, "download_and_verify", side_effect=[A.ArtifactError("network"), {"verified": True}]):
                with self.assertRaisesRegex(A.ArtifactError, "network"):
                    A.publish_release(
                        manifest_path, archive, "evidence-test-m-test", committed,
                        plan(), root / "raw", root,
                    )
                self.assertEqual(A.publish_release(
                    manifest_path, archive, "evidence-test-m-test", committed,
                    plan(), root / "raw", root,
                ), {"verified": True})
            self.assertEqual(committed.read_bytes(), manifest_path.read_bytes())


class LedgerReferenceTest(unittest.TestCase):
    def setUp(self):
        A.EXPERIMENT_ROW_VALIDATORS["E-99"] = lambda row, manifest: None

    def tearDown(self):
        A.EXPERIMENT_ROW_VALIDATORS.pop("E-99", None)

    def test_cold_reader_qualification_row_binds_shape_inputs_counts_and_identity(self):
        root = Path(__file__).resolve().parent.parent
        models = A.load_json(root / "experiments" / "e09" / "models.json")
        family = models["qualification_profiles"][0]
        profile = models["profiles"][family]
        suite_path = root / "experiments" / "e09" / "cold_reader_cases.json"
        suite = A.load_json(suite_path)
        key = {
            "tier": "qualification",
            "profile": family,
            "profile_sha256": A.sha256_bytes(A.canonical(profile).encode()),
            "harness_sha256": A.sha256_file(root / "experiments" / "e09" / "harness.py"),
            "catalog_sha256": A.sha256_file(root / "experiments" / "e09" / "catalog.json"),
            "suite_sha256": A.sha256_file(suite_path),
            "freeze_sha256": A.sha256_file(root / "experiments" / "e09" / "freeze.json"),
        }
        completed_at = "2026-08-24T00:00:00+00:00"
        row = {
            "run_id": "pending",
            "date": completed_at,
            "schema_version": 2,
            "type": "experiment",
            "experiment": "E-09-cold-reader",
            "family": family,
            "tier": "qualification",
            "passed": True,
            "started_calls": len(suite["qualification"]["cases"])
            * suite["qualification"]["repetitions_per_profile"],
            "assertions": A.qualification_assertion_count(suite),
            "failed_assertions": 0,
            "errors": 0,
            "key": key,
            "raw_dir": "experiments/e09/raw/qualification/cr-"
            + A.sha256_bytes(A.canonical(key).encode())[:16],
            "completed_at": completed_at,
        }
        payload = {key: value for key, value in row.items() if key not in ("run_id", "date")}
        row["run_id"] = A.content_run_id(payload, completed_at)
        A.validate_cold_reader_qualification_row(row, root)
        changed = json.loads(json.dumps(row))
        changed["assertions"] -= 1
        with self.assertRaises(A.ArtifactError):
            A.validate_cold_reader_qualification_row(changed, root)
        changed = json.loads(json.dumps(row))
        changed["unexpected"] = True
        with self.assertRaisesRegex(A.ArtifactError, "wrong fields"):
            A.validate_cold_reader_qualification_row(changed, root)
        historical = json.loads(json.dumps(row))
        historical["key"]["freeze_sha256"] = "0" * 64
        historical["raw_dir"] = "experiments/e09/raw/qualification/cr-" \
            + A.sha256_bytes(A.canonical(historical["key"]).encode())[:16]
        payload = {
            key: value for key, value in historical.items() if key not in ("run_id", "date")
        }
        historical["run_id"] = A.content_run_id(payload, completed_at)
        A.validate_cold_reader_qualification_row(historical, root)
        with self.assertRaisesRegex(A.ArtifactError, "current inputs"):
            A.validate_cold_reader_qualification_row(
                historical, root, require_current_inputs=True
            )
        old_harness = json.loads(json.dumps(row))
        old_harness["key"]["harness_sha256"] = "0" * 64
        old_harness["raw_dir"] = "experiments/e09/raw/qualification/cr-" \
            + A.sha256_bytes(A.canonical(old_harness["key"]).encode())[:16]
        payload = {
            key: value for key, value in old_harness.items() if key not in ("run_id", "date")
        }
        old_harness["run_id"] = A.content_run_id(payload, completed_at)
        A.validate_cold_reader_qualification_row(old_harness, root)
        with self.assertRaisesRegex(A.ArtifactError, "current inputs"):
            A.validate_cold_reader_qualification_row(
                old_harness, root, require_current_inputs=True
            )

    def test_e09_result_row_requires_complete_typed_schema_and_content_identity(self):
        row = e09_result_row()
        A.validate_e09_result_row(row, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["arms"]["control"]["runs"][0]["task_successes"] = 1
        with self.assertRaisesRegex(A.ArtifactError, "wrong fields"):
            A.validate_e09_result_row(changed, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["arms"]["control"]["runs"][0]["coverage"] = "fabricated"
        with self.assertRaisesRegex(A.ArtifactError, "finite number"):
            A.validate_e09_result_row(changed, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["claim_checks"]["C19"]["mean_gain"] = 1
        with self.assertRaisesRegex(A.ArtifactError, "claim checks differ"):
            A.validate_e09_result_row(changed, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["arms"]["control"]["coverage"]["values"][0] = 1
        with self.assertRaises(A.ArtifactError):
            A.validate_e09_result_row(changed, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["arms"]["treatment"]["runs"][0]["coverage_per_100_contract_tokens"] = 999
        with self.assertRaisesRegex(A.ArtifactError, "run metrics differ"):
            A.validate_e09_result_row(changed, e09_manifest())
        changed = json.loads(json.dumps(row))
        changed["completed_at"] = "2026-08-24T00:00:01+00:00"
        changed["date"] = changed["completed_at"]
        with self.assertRaisesRegex(A.ArtifactError, "run_id differs"):
            A.validate_e09_result_row(changed, e09_manifest())

    def test_e09_compact_result_requires_exactly_one_row_per_family(self):
        fable = e09_result_row()
        kimi = json.loads(json.dumps(fable))
        kimi["family"] = "kimi-subject"
        payload = {key: value for key, value in kimi.items() if key not in ("run_id", "date")}
        kimi["run_id"] = A.content_run_id(payload, kimi["completed_at"])
        A.validate_compact_result_rows([fable, kimi], [fable, kimi], "result.json")
        with self.assertRaisesRegex(A.ArtifactError, "exactly one row"):
            A.validate_compact_result_rows([fable, kimi, fable], [fable, kimi, fable], "result.json")

    def test_ledger_receipt_must_match_manifest_attestations_and_results(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, local_manifest = ArtifactPackTest().pack_at(root, "ledger")
            payload = A.load_json(local_manifest)
            retarget_manifest_experiment(payload, "E-99")
            local_manifest.unlink()
            A.write_json_exclusive(local_manifest, payload)
            manifest_path = root / "experiments" / "e99" / "artifacts" / "m-test.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_bytes(local_manifest.read_bytes())
            manifest = A.load_json(manifest_path)
            results_path = root / "experiments" / "e99" / "results" / "m-test.json"
            artifact = {
                "archive_sha256": manifest["archive"]["sha256"],
                "attestations": {
                    "archive": {
                        "asset_name": manifest["release"]["archive_asset_name"],
                        "sha256": manifest["archive"]["sha256"],
                    },
                    "release": {
                        "release_id": 42,
                        "repository_id": manifest["repository"]["id"],
                        "tag": manifest["release"]["tag"],
                    },
                },
                "manifest_path": str(manifest_path.relative_to(root)),
                "manifest_sha256": A.sha256_file(manifest_path),
                "release_id": 42,
                "release_tag": manifest["release"]["tag"],
                "verified": True,
            }
            row = {
                "run_id": "r-test",
                "schema_version": 2,
                "type": "experiment",
                "experiment": "E-99",
                "batch_id": "m-test",
                "freeze_sha256": manifest["freeze_sha256"],
                "artifact": artifact,
                "results_path": str(results_path.relative_to(root)),
            }
            results_path.parent.mkdir(parents=True)
            results_path.write_text(json.dumps({"schema_version": 2, "lines": [row]}) + "\n", encoding="utf-8")
            ledger = root / "ledger" / "runs.jsonl"
            write_test_ledger(ledger, [row])
            verified_list = root / "verified-manifests.txt"
            self.assertEqual(A.verify_ledger_references(
                root, "mlamp/meta-skills", verified_manifest_list=verified_list
            ), {
                "artifact_ledger_rows_verified": 1, "verified": True,
            })
            A.EXPERIMENT_ROW_VALIDATORS.pop("E-99")
            try:
                with self.assertRaisesRegex(A.ArtifactError, "no trusted result-row validator"):
                    A.verify_ledger_references(root, "mlamp/meta-skills")
            finally:
                A.EXPERIMENT_ROW_VALIDATORS["E-99"] = lambda row, manifest: None
            self.assertEqual(verified_list.read_bytes(), artifact["manifest_path"].encode() + b"\0")
            self.assertTrue(A.require_manifest_list_membership(
                verified_list, artifact["manifest_path"]
            )["verified_through_ledger"])
            verified_list.unlink()
            verified_list.write_bytes(b"verified\x1ephantom\0")
            with self.assertRaisesRegex(A.ArtifactError, "not verified through the ledger"):
                A.require_manifest_list_membership(verified_list, "phantom")
            self.assertTrue(A.require_manifest_list_membership(
                verified_list, "verified\x1ephantom"
            )["verified_through_ledger"])
            verified_list.unlink()
            verified_list.write_bytes(b"unterminated")
            with self.assertRaisesRegex(A.ArtifactError, "not NUL-terminated"):
                A.require_manifest_list_membership(verified_list, "unterminated")
            remote_receipt = {key: value for key, value in artifact.items() if key != "manifest_path"}
            with mock.patch.object(A, "download_and_verify", return_value=remote_receipt) as remote:
                self.assertEqual(A.verify_ledger_references(
                    root, "mlamp/meta-skills", verify_remote=True
                )["artifact_ledger_rows_verified"], 1)
            remote.assert_called_once_with(
                manifest, manifest_path.resolve(), expected_repository="mlamp/meta-skills"
            )
            wrong_remote = {
                **remote_receipt,
                "release_id": 43,
                "attestations": {
                    **remote_receipt["attestations"],
                    "release": {**remote_receipt["attestations"]["release"], "release_id": 43},
                },
            }
            with mock.patch.object(A, "download_and_verify", return_value=wrong_remote):
                with self.assertRaisesRegex(A.ArtifactError, "remote verification"):
                    A.verify_ledger_references(root, "mlamp/meta-skills", verify_remote=True)
            extra = {**row, "run_id": "r-unledgered"}
            results_path.write_text(
                json.dumps({"schema_version": 2, "lines": [row, extra]}) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(A.ArtifactError, "complete ledger set"):
                A.verify_ledger_references(root, "mlamp/meta-skills")
            results_path.write_text(
                json.dumps({"schema_version": 2, "lines": [row]}) + "\n", encoding="utf-8"
            )
            row["freeze_sha256"] = "0" * 64
            write_test_ledger(ledger, [row])
            with self.assertRaisesRegex(A.ArtifactError, "freeze_sha256 differs"):
                A.verify_ledger_references(root, "mlamp/meta-skills")
            row["freeze_sha256"] = manifest["freeze_sha256"]
            row["artifact"]["release_tag"] = "different-tag"
            write_test_ledger(ledger, [row])
            with self.assertRaisesRegex(A.ArtifactError, "release tag differs"):
                A.verify_ledger_references(root, "mlamp/meta-skills")

    def test_every_nonlegacy_measured_row_requires_bound_artifact_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            ledger = root / "ledger" / "runs.jsonl"
            row = {"run_id": "r-new", "type": "experiment", "experiment": "E-99"}
            write_test_ledger(ledger, [row])
            with self.assertRaisesRegex(A.ArtifactError, "requires artifact evidence"):
                A.verify_ledger_references(root)
            write_test_ledger(ledger, [])
            self.assertEqual(A.verify_ledger_references(root)["artifact_ledger_rows_verified"], 0)
            legacy = pinned_legacy_rows()
            legacy[0]["notes"] = "rewritten"
            ledger.write_text("".join(A.canonical(item) + "\n" for item in legacy), encoding="utf-8")
            with self.assertRaisesRegex(A.ArtifactError, "legacy artifactless row differs"):
                A.verify_ledger_references(root)

    def test_ledger_requires_every_pinned_legacy_cold_reader_row(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rows = pinned_legacy_rows()
            missing = next(iter(A.LEGACY_COLD_READER_RUNS))
            rows = [row for row in rows if row["run_id"] != missing]
            ledger = root / "ledger" / "runs.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(
                "".join(A.canonical(row) + "\n" for row in rows), encoding="utf-8"
            )
            with self.assertRaisesRegex(A.ArtifactError, "missing pinned legacy cold-reader rows"):
                A.verify_ledger_references(root)

    def test_ledger_must_extend_the_trusted_baseline_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            ledger = root / "ledger" / "runs.jsonl"
            baseline = root / "baseline.jsonl"
            write_test_ledger(ledger, [])
            baseline.write_bytes(ledger.read_bytes())
            self.assertTrue(A.verify_ledger_references(root, baseline_ledger=baseline)["verified"])
            ledger.write_bytes(ledger.read_bytes().replace(b'"E-07"', b'"E-70"', 1))
            with self.assertRaisesRegex(A.ArtifactError, "append-only extension"):
                A.verify_ledger_references(root, baseline_ledger=baseline)

    def test_ledger_experiment_batch_and_paths_must_match_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            _, local_manifest = ArtifactPackTest().pack_at(root, "ledger")
            payload = A.load_json(local_manifest)
            retarget_manifest_experiment(payload, "E-99")
            local_manifest.unlink()
            A.write_json_exclusive(local_manifest, payload)
            manifest_path = root / "experiments" / "e99" / "artifacts" / "m-test.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_bytes(local_manifest.read_bytes())
            artifact = {
                "archive_sha256": payload["archive"]["sha256"],
                "attestations": {
                    "archive": {"asset_name": payload["release"]["archive_asset_name"],
                                "sha256": payload["archive"]["sha256"]},
                    "release": {"release_id": 42, "repository_id": payload["repository"]["id"],
                                "tag": payload["release"]["tag"]},
                },
                "manifest_path": str(manifest_path.relative_to(root)),
                "manifest_sha256": A.sha256_file(manifest_path),
                "release_id": 42,
                "release_tag": payload["release"]["tag"],
                "verified": True,
            }
            row = {"run_id": "r-test", "schema_version": 2, "type": "experiment", "experiment": "E-98",
                   "batch_id": "m-test", "artifact": artifact,
                   "results_path": "experiments/e98/results/m-test.json"}
            results = root / row["results_path"]
            results.parent.mkdir(parents=True)
            results.write_text(json.dumps({"schema_version": 2, "lines": [row]}) + "\n", encoding="utf-8")
            ledger = root / "ledger" / "runs.jsonl"
            write_test_ledger(ledger, [row])
            with self.assertRaisesRegex(A.ArtifactError, "experiment differs"):
                A.verify_ledger_references(root)


if __name__ == "__main__":
    unittest.main()
