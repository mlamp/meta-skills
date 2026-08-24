#!/usr/bin/env python3

import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from experiments import artifacts as A


def plan():
    return {
        "schema_version": 1,
        "repository": {"id": 1337622598, "name": "mlamp/meta-skills"},
        "experiment": "E-test",
        "batch_id": "m-test",
        "raw_root": "experiments/e-test/raw/measured/m-test",
        "frozen_commit": "a" * 40,
        "freeze_sha256": "b" * 64,
        "packager_commit": "a" * 40,
        "provenance": {"design.md": "c" * 64},
        "schedule": {"test_sha256": "d" * 64},
        "expected_members": [
            {"path": "interviews/one.json", "kind": "interview"},
            {"path": "record-manifest.jsonl", "kind": "call_manifest"},
        ],
        "expected_counts": {"call_manifest": 1, "interview": 1},
        "credential_env_names": ["TEST_ARTIFACT_API_KEY"],
        "forbidden_patterns": [{"id": "private", "regex": "PRIVATE-MARKER"}],
        "execution": {},
        "exclusions": [],
        "release": {
            "tag": "evidence-test-m-test",
            "archive_asset_name": "m-test.raw.tar.gz",
            "manifest_asset_name": "m-test.manifest.json",
        },
        "supersedes": None,
    }


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
        bad = plan()
        bad["expected_members"] = [{"path": "../secret.json", "kind": "raw"}]
        with self.assertRaisesRegex(A.ArtifactError, "unsafe"):
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
            with tarfile.open(archive, "w:gz") as handle:
                info = tarfile.TarInfo("../escape.json")
                info.size = 2
                handle.addfile(info, io.BytesIO(b"{}"))
            payload = A.load_json(manifest)
            payload["archive"]["sha256"] = A.sha256_file(archive)
            payload["archive"]["bytes"] = archive.stat().st_size
            manifest.unlink()
            A.write_json_exclusive(manifest, payload)
            with self.assertRaisesRegex(A.ArtifactError, "unsafe"):
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

    def test_draft_lookup_resolves_release_id_before_rest_read(self):
        completed = mock.Mock(returncode=0, stdout='{"databaseId":42}', stderr="")
        with mock.patch.object(A.subprocess, "run", return_value=completed), \
             mock.patch.object(A, "gh_json", return_value={"id": 42}) as gh:
            self.assertEqual(A.release_by_tag_any_state("owner/repo", "tag"), {"id": 42})
        gh.assert_called_once_with("owner/repo", "releases/42")

    def test_stage_resume_reuploads_exact_draft_assets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            release = self.release(manifest_path, archive)
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "verify_repository_identity", return_value={"default_branch": "main"}), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "verify_superseded_release"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "wait_for_server_assets", return_value=release), \
                 mock.patch.object(A, "run", return_value="") as runner:
                receipt = A.stage_release(manifest_path, archive)
            self.assertEqual(receipt, {"release_id": 42, "state": "draft", "tag": "evidence-test-m-test"})
            command = runner.call_args.args[0]
            self.assertEqual(command[:4], ["gh", "release", "upload", "evidence-test-m-test"])
            self.assertIn("--clobber", command)

    def test_publish_retry_accepts_matching_immutable_release_and_copies_manifest(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive, manifest_path = self.packed(root)
            committed = root / "tracked" / "manifest.json"
            release = self.release(manifest_path, archive, draft=False, immutable=True)
            receipt = {"verified": True, "release_id": 42}
            with mock.patch.object(A, "require_immutable_releases"), \
                 mock.patch.object(A, "verify_repository_identity"), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "gh_json", return_value=release), \
                 mock.patch.object(A, "download_and_verify", return_value=receipt) as download, \
                 mock.patch.object(A, "run") as runner:
                self.assertEqual(A.publish_release(
                    manifest_path, archive, "evidence-test-m-test", committed
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
                 mock.patch.object(A, "verify_repository_identity"), \
                 mock.patch.object(A, "commit_is_on_default_branch"), \
                 mock.patch.object(A, "release_by_tag_any_state", return_value=release), \
                 mock.patch.object(A, "gh_json", return_value=release), \
                 mock.patch.object(A, "download_and_verify", side_effect=[A.ArtifactError("network"), {"verified": True}]):
                with self.assertRaisesRegex(A.ArtifactError, "network"):
                    A.publish_release(manifest_path, archive, "evidence-test-m-test", committed)
                self.assertEqual(A.publish_release(
                    manifest_path, archive, "evidence-test-m-test", committed
                ), {"verified": True})
            self.assertEqual(committed.read_bytes(), manifest_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
