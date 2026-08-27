#!/usr/bin/env python3

import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("e09_harness", HERE / "harness.py")
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)


class FrozenInputsTest(unittest.TestCase):
    def test_all_json_files_parse(self):
        for path in H.DATA_FILES.values():
            self.assertIsInstance(H.load_json(path), dict, path.name)

    def test_measured_id_hashes_complete_validated_freeze(self):
        first = H.freeze_payload()
        first["frozen_at"] = "2026-08-24"
        second = {**first, "frozen_at": "2026-08-25"}
        with mock.patch.object(H, "load_json", return_value=first):
            first_id = H.measured_id()
        with mock.patch.object(H, "load_json", return_value=second):
            second_id = H.measured_id()
        self.assertNotEqual(first_id, second_id)
        with self.assertRaisesRegex(H.HarnessError, "invalid schema"):
            H.validate_freeze_payload({**first, "unexpected": True})
        with self.assertRaisesRegex(H.HarnessError, "invalid schema"):
            H.validate_freeze_payload({**first, "schema_version": True})

    def test_source_hashes_match(self):
        persona = H.load_json(H.DATA_FILES["persona.json"])
        for source in persona["source_artifacts"]:
            self.assertEqual(H.sha256(H.ROOT / source["path"]), source["sha256"])

    def test_stage1_evidence_names_exact_frozen_sources(self):
        persona = H.load_json(H.DATA_FILES["persona.json"])
        stage1 = H.load_json(H.DATA_FILES["persona-stage1.json"])
        source_paths = {source["path"] for source in persona["source_artifacts"]}
        for preference in stage1["preferences"]:
            for evidence in preference["source_evidence"]:
                source_path, separator, detail = evidence.partition(": ")
                self.assertEqual(separator, ": ", evidence)
                self.assertIn(source_path, source_paths, evidence)
                self.assertTrue(detail, evidence)

    def test_catalog_is_closed_and_ordered(self):
        catalog = H.load_json(H.DATA_FILES["catalog.json"])
        ids = [entry["id"] for entry in catalog["entries"]]
        self.assertEqual(ids, [f"U{i:02d}" for i in range(1, 7)])
        self.assertEqual(catalog["overlap_precedence"], ids)
        used = {name for entry in catalog["entries"] for name in entry["sublabels"]}
        self.assertEqual(set(catalog["sublabel_definitions"]), used)
        rendered = H.catalog_markdown(catalog)
        self.assertIn("abstraction = an abstract or evaluative label", rendered)

    def test_every_mapping_was_curator_confirmed(self):
        persona = H.load_json(H.DATA_FILES["persona.json"])
        self.assertEqual(len(persona["catalog_mapping"]), 10)
        self.assertTrue(all(row["curator_confirmed"] for row in persona["catalog_mapping"]))
        resolved = sorted({uid for row in persona["catalog_mapping"] for uid in row["resolved_catalog_ids"]})
        self.assertEqual(resolved, persona["relevant_catalog_ids"])
        self.assertEqual([row["evidence_id"] for row in persona["evidence_mapping"]],
                         ["I01", "I02", "I03", "I04", "O01", "O02", "O03", "O04", "O05", "O06", "O07", "O08", "O09"])

    def test_preference_rejection_is_not_mapping_confirmation(self):
        persona = H.load_json(H.DATA_FILES["persona.json"])
        v10 = next(row for row in persona["relevance_curator"] if row["preference_id"] == "V10")
        mapped = next(row for row in persona["catalog_mapping"] if row["preference_id"] == "V10")
        self.assertTrue(v10["preference_rejected"])
        self.assertEqual(mapped["resolved_catalog_ids"], [])

    def test_freeze_payload_covers_every_registered_input(self):
        payload = H.freeze_payload()
        expected = {str(path.relative_to(H.ROOT)) for path in H.FREEZE_INPUTS}
        self.assertEqual(set(payload["files"]), expected)

    def test_adapter_smoke_key_binds_case_suite(self):
        first = H.adapter_smoke_namespace()[1]
        with mock.patch.object(H, "sha256", side_effect=lambda path: (
            "changed" if path == H.DATA_FILES["cold_reader_cases.json"] else H.sha256_value(str(path))
        )):
            second = H.adapter_smoke_namespace()[1]
        self.assertNotEqual(first["suite_sha256"], second["suite_sha256"])

    def test_frozen_gate_compares_every_working_byte_with_head(self):
        old_root, old_e09, old_inputs = H.ROOT, H.E09, H.FREEZE_INPUTS
        with tempfile.TemporaryDirectory() as tmp:
            try:
                root = Path(tmp)
                H.ROOT = root
                H.E09 = root / "experiments" / "e09"
                source = H.E09 / "design.md"
                freeze = H.E09 / "freeze.json"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"design\n")
                freeze.write_bytes(b"freeze\n")
                H.FREEZE_INPUTS = (source,)

                def committed(command, **kwargs):
                    relative = command[-1].split(":", 1)[1]
                    data = b"design\n" if relative.endswith("design.md") else b"freeze\n"
                    return mock.Mock(returncode=0, stdout=data)

                with mock.patch.object(H.subprocess, "run", side_effect=committed):
                    H.require_worktree_matches_frozen_commit("a" * 40, "gate")
                    source.write_bytes(b"changed\n")
                    with self.assertRaisesRegex(H.HarnessError, "differs from the frozen commit"):
                        H.require_worktree_matches_frozen_commit("a" * 40, "gate")
            finally:
                H.ROOT, H.E09, H.FREEZE_INPUTS = old_root, old_e09, old_inputs

    def test_provider_gates_bind_working_source_before_input_reads(self):
        for gate in (H.ensure_qualification_start_gate, H.ensure_measured_gate):
            with self.subTest(gate=gate.__name__), \
                 mock.patch.object(H, "git", return_value="a" * 40), \
                 mock.patch.object(H, "require_exact_frozen_head"), \
                 mock.patch.object(
                     H, "require_worktree_matches_frozen_commit",
                     side_effect=H.HarnessError("source sentinel"),
                 ) as source, mock.patch.object(H, "validate_inputs") as inputs, \
                 self.assertRaisesRegex(H.HarnessError, "source sentinel"):
                gate()
            source.assert_called_once()
            inputs.assert_not_called()

    def test_smoke_commands_secure_namespace_before_provider_call(self):
        cases = (
            (
                H.cmd_cold_reader,
                mock.Mock(tier="smoke", profiles=["haiku-reader"]),
                "run_with_transport_retry",
            ),
            (H.cmd_adapter_smoke, mock.Mock(), "call_tool"),
        )
        for command, args, provider_name in cases:
            attempt = H.RAW / "smoke" / "test-attempt"
            with self.subTest(command=command.__name__), \
                 mock.patch.object(H, "next_smoke_attempt", return_value=attempt), \
                 mock.patch.object(
                     H, "ensure_local_namespace",
                     side_effect=[None, H.HarnessError("namespace sentinel")],
                 ) as namespace, mock.patch.object(H, provider_name) as provider, \
                 self.assertRaisesRegex(H.HarnessError, "namespace sentinel"):
                command(args)
            self.assertEqual(namespace.call_count, 2)
            self.assertEqual(namespace.call_args_list[-1].args[0], attempt)
            provider.assert_not_called()

    def test_artifact_spec_covers_provider_credentials_and_repository_identity(self):
        spec = H.load_json(H.DATA_FILES["artifact-spec.json"])
        models = H.load_json(H.DATA_FILES["models.json"])
        credentials = {
            row.get("credential_env") for row in models["profiles"].values()
            if row.get("credential_env")
        }
        self.assertLessEqual(credentials, set(spec["credential_env_names"]))
        self.assertEqual(spec["repository"], {"id": 1337622598, "name": "mlamp/meta-skills"})
        pattern_ids = {row["id"] for row in spec["forbidden_patterns"]}
        self.assertTrue({"host_windows_path", "host_uuid", "host_project_id"} <= pattern_ids)

    def test_sanitizer_blocks_real_leaks_without_blocking_task_prose(self):
        """D-033: the pack-time patterns must catch real secrets and host paths while
        letting through the vocabulary the frozen tasks ask for. A false positive here
        aborts artifact-pack and destroys a measured batch; a false negative publishes
        a secret. Both directions are pinned."""
        spec = H.load_json(H.DATA_FILES["artifact-spec.json"])
        patterns = {row["id"]: re.compile(row["regex"]) for row in spec["forbidden_patterns"]}

        def hits(text):
            return [name for name, rx in patterns.items() if rx.search(text)]

        must_block = [
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "bearer sk-ant-api03-QWxhZGRpbjpvcGVuIHNlc2FtZQ",
            "Authorization: Bearer a1b2c3d4e5f60718",
            "Bearer keyO4WrHtEc31nY7z",
            "Bearer thisisaverylongsecretvaluewithnodigits",
            "DEEPINFRA_API_KEY=di-9f3a2b7c4e1d8a6b5c0f",
            'GITHUB_TOKEN="ghp_abc123XYZ456def789"',
            "AUTH_TOKEN=<ghp_16C7e42F292c6912E7710c838347Ae178B4a>",
            "DEEPINFRA_API_KEY=***9f3a7c21b8e04d6fa1c5e7b90d2f4a83",
            "AUTH_TOKEN=REDACTED-ghp_16C7e42F292c6912E7710c838347Ae178B4a",
            "AUTH_TOKEN=**ghp_16C7e42F292c6912E7710c838347Ae178B4a**",
            "AUTH_TOKEN=REDACTED.ghp_16C7e42F292c6912E7710c838347Ae178B4a",
            "/Users/margus/_DEV/_AGENTIC/meta-skills",
            "/users/margus/_DEV/_AGENTIC/meta-skills",
            "/home/margus/.config/app",
            "/Users/Shared/thing",
            "/var/folders/4n/_9x49yyj2nbgwmg1qqljxqk00000gn/T",
            "/private/var/folders/qd/8k2n7x9s1234/T/x",
            "/tmp/claude-mcp-browser-bridge-margus",
            "/private/tmp/claude-mcp-browser-bridge-margus",
            "/tmp/e09-codex-7f3a91bc",
            "e09-tool-f533t68y",
        ]
        must_pass = [
            "Redact the Bearer token before logging.",
            "Use a Bearer token.",
            "Bearer credentials",
            "Bearer authorization",
            "Bearer <SECRET>",
            "Bearer <token>",
            "Bearer $ACCESS_TOKEN",
            "Bearer ***",
            "Bearer your-token",
            "Strip the Authorization header from log output.",
            "Set AUTH_TOKEN=<redacted> in the log formatter.",
            "AUTH_TOKEN=<redacted>.",
            "export API_TOKEN=$MY_TOKEN",
            "Use ${AUTH_TOKEN} from the environment.",
            'PASSWORD=""',
            "AUTH_TOKEN=***",
            "SESSION_TOKEN=REDACTED",
            "API_TOKEN=null",
            "/home/user/.local/share/app/store.db",
            "/Users/you/Library/Application Support/app",
            "/home/username/data",
            "/home/ubuntu/app/store.db",
            "~/.local/share/app/store.db",
            "./svc --config /tmp/config.yaml",
            "/tmp/app.sqlite3",
            "/tmp/backup-2026-08-25.db",
            "/tmp/dump-1.sql",
            "/tmp/restore.db",
            "Restore from store.db.bak beside the database.",
            "Cap attempts at three and drop the token from the log message.",
            "<HOST_PATH>",
            "<PROJECT_ID>",
        ]
        for text in must_block:
            self.assertTrue(hits(text), f"leak not blocked: {text}")
        for text in must_pass:
            self.assertEqual([], hits(text), f"task prose over-blocked: {text}")

    def test_pr_ci_separates_candidate_code_from_release_credentials(self):
        workflow = (H.ROOT / ".github" / "workflows" / "verify-experiment-artifacts.yml").read_text(
            encoding="utf-8"
        )
        candidate, trusted = workflow.split("  trusted-verification:", 1)
        self.assertIn("  pull_request:\n", candidate)
        self.assertIn("pull_request_target:", candidate)
        self.assertIn('      - "ledger/**"', candidate)
        self.assertIn("if: github.event_name == 'pull_request' || github.event_name == 'push'", candidate)
        self.assertNotIn("GH_TOKEN", candidate)
        self.assertIn("persist-credentials: false", candidate)
        self.assertIn("if: github.event_name == 'pull_request_target' || github.event_name == 'push'", trusted)
        self.assertIn("github.event.pull_request.base.sha", trusted)
        self.assertIn("github.event.pull_request.merge_commit_sha", trusted)
        self.assertIn("github.event.pull_request.head.sha", trusted)
        self.assertIn('git -C candidate rev-parse HEAD^2', trusted)
        self.assertIn("GH_TOKEN", trusted)
        self.assertIn('verifier_root="$GITHUB_WORKSPACE/trusted"', trusted)
        self.assertIn("--verify-remote", trusted)
        self.assertIn("--baseline-ledger", trusted)
        self.assertIn("--verified-manifest-list", trusted)
        self.assertIn("manifest-list-contains", trusted)
        self.assertNotIn("grep -Fqx", trusted)
        manifest_find = next(line for line in trusted.splitlines() if "find \"$candidate_root/experiments\"" in line)
        self.assertIn("-print0", manifest_find)
        self.assertNotIn("-type f", manifest_find)
        self.assertIn("GITHUB_EVENT_BEFORE: ${{ github.event.before }}", trusted)
        self.assertNotIn("< <(find", trusted)


class ArmIsolationTest(unittest.TestCase):
    def test_treatment_is_one_insertion_replacement(self):
        prompts = H.load_json(H.DATA_FILES["prompts.json"])["interview"]
        control = H.render_interview("control")
        treatment = H.render_interview("treatment")
        insertion = prompts["treatment_slot"] + "\n\n" + H.catalog_markdown().rstrip()
        self.assertEqual(treatment, control.replace(prompts["control_slot"], insertion))

    def test_control_has_no_catalog_identifiers_labels_or_confirmations(self):
        control = H.render_interview("control")
        catalog = H.load_json(H.DATA_FILES["catalog.json"])
        for entry in catalog["entries"]:
            self.assertNotIn(entry["id"], control)
            self.assertNotIn(entry["label"], control)
        # Natural inventory language may contain words such as "filler". The
        # catalog-only machine labels must still be absent.
        self.assertNotIn("hedge_stack", control)
        self.assertNotIn("unsupported_result", control)
        self.assertNotIn("Sublabels:", control)
        self.assertNotIn("confirms U", control)

    def test_treatment_uses_exact_qualification_catalog_renderer(self):
        treatment = H.render_interview("treatment")
        block = H.catalog_markdown().rstrip()
        self.assertEqual(treatment.count(block), 1)
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["qualification"]["cases"][0]
        self.assertIn(block, H.case_prompt(case))

    def test_treatment_slot_does_not_name_scored_or_rejected_ids(self):
        slot = H.load_json(H.DATA_FILES["prompts.json"])["interview"]["treatment_slot"].lower()
        self.assertNotIn("confirm", slot)
        self.assertNotIn("rejects u", slot)
        self.assertNotIn("u01", slot)

    def test_contract_format_states_the_exact_validator_invariant(self):
        contract_format = H.load_json(H.DATA_FILES["prompts.json"])["interview"]["contract_format"]
        self.assertIn("no headings", contract_format)
        self.assertIn("exactly the rules[].text values, in order", contract_format)
        self.assertIn("one per line, and nothing else", contract_format)

    def test_control_tool_schema_does_not_leak_catalog(self):
        schema = H.canonical(H.contract_schema("control"))
        self.assertNotIn("U01", schema)
        self.assertNotIn("catalog", schema)
        treatment = H.canonical(H.contract_schema("treatment"))
        self.assertIn("U01", treatment)
        self.assertIn("selected_catalog_ids", treatment)


class StructuredInterfaceTest(unittest.TestCase):
    def test_case_schemas_reject_incomplete_payloads(self):
        suite = H.load_json(H.DATA_FILES["cold_reader_cases.json"])
        for case in suite["qualification"]["cases"]:
            errors = H.validate_schema({"case_id": case["id"]}, H.case_schema(case))
            self.assertTrue(errors, case["id"])

    def test_smoke_schema_exercises_later_strict_keywords(self):
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["smoke"]["case"]
        schema = H.case_schema(case)
        answers = schema["properties"]["answers"]
        self.assertTrue(answers["uniqueItems"])
        self.assertEqual(answers["minItems"], answers["maxItems"])
        self.assertEqual(answers["items"]["properties"]["item_id"]["minLength"], 1)
        self.assertIn("null", answers["items"]["properties"]["pattern_id"]["type"])

    def test_schema_rejects_extra_fields(self):
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["qualification"]["cases"][1]
        payload = {"case_id": case["id"], "answers": [
            {"item_id": row["item_id"], "pattern_id": row["pattern_id"], "sublabel": row["sublabel"]}
            for row in case["expected"]
        ], "explanation": "not allowed"}
        self.assertTrue(any("unexpected explanation" in item for item in H.validate_schema(payload, H.case_schema(case))))

    def test_substitute_verdicts_cover_frozen_candidates_once_in_order(self):
        valid = {"verdicts": [
            {"candidate_id": "c1", "pattern_id": None},
            {"candidate_id": "c2", "pattern_id": "U01"},
        ]}
        H.validate_substitute_payload(valid, ["c1", "c2"])
        with self.assertRaises(H.FormatError):
            H.validate_substitute_payload({"verdicts": [valid["verdicts"][0], valid["verdicts"][0]]}, ["c1", "c2"])

    def test_classification_order_is_not_semantic(self):
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["qualification"]["cases"][1]
        payload = {"case_id": case["id"], "answers": list(reversed(case["expected"]))}
        assertions = H.grade_case(case, payload)
        self.assertTrue(all(item["pass"] for item in assertions))

    def test_precedence_order_is_semantic(self):
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["qualification"]["cases"][0]
        payload = {"case_id": case["id"], **case["expected"]}
        self.assertTrue(all(item["pass"] for item in H.grade_case(case, payload)))
        payload["precedence"] = list(reversed(payload["precedence"]))
        failed = [item["assertion"] for item in H.grade_case(case, payload) if not item["pass"]]
        self.assertEqual(failed, ["precedence"])

    def test_parser_requires_exactly_one_tool_call(self):
        event = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": H.CLAUDE_STRUCTURED_TOOL, "input": {"ok": True}}
        ]}}
        payload, _, _ = H.parse_claude_stream(json.dumps(event), H.CLAUDE_STRUCTURED_TOOL)
        self.assertEqual(payload, {"ok": True})
        with self.assertRaises(H.FormatError):
            H.parse_claude_stream(json.dumps(event) + "\n" + json.dumps(event), H.CLAUDE_STRUCTURED_TOOL)
        with self.assertRaises(H.FormatError):
            H.parse_claude_stream('{"type":"assistant","type":"result"}', H.CLAUDE_STRUCTURED_TOOL)

    def test_deepinfra_strict_tool_argument_failure_uses_format_protocol(self):
        raw = {"choices": [{"message": {"tool_calls": [{"function": {
            "name": H.TOOL_NAME, "arguments": '{"value":1,"value":2}',
        }}]}}]}
        profile = {"model": "test", "temperature": 0, "provider": "test"}
        with mock.patch.object(H, "deepinfra_request", return_value=raw), \
             self.assertRaisesRegex(H.FormatError, "invalid tool arguments"):
            H.call_deepinfra_tool(profile, "prompt", {"type": "object"})
        with mock.patch.object(H, "deepinfra_request", return_value=[]), \
             self.assertRaisesRegex(H.FormatError, "invalid response object"):
            H.call_deepinfra_tool(profile, "prompt", {"type": "object"})
        with mock.patch.object(H, "deepinfra_request", return_value={"choices": [None]}), \
             self.assertRaisesRegex(H.FormatError, "exactly one required tool call"):
            H.call_deepinfra_tool(profile, "prompt", {"type": "object"})

    def test_deepinfra_malformed_http_json_is_nonretryable_format_failure(self):
        profile = {
            "api_base": "https://example.invalid",
            "timeout_seconds": 1,
            "credential_env": "TEST_KEY",
        }
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"value":1,"value":2}'
        with mock.patch.object(H, "credential", return_value="secret"), \
             mock.patch.object(H.urllib.request, "urlopen", return_value=response), \
             self.assertRaisesRegex(H.FormatError, "invalid strict JSON"):
            H.deepinfra_request(profile, {"test": True})
        failure = H.FormatError("bad format")
        with mock.patch.object(H, "call_tool", side_effect=failure) as caller, \
             self.assertRaises(H.FormatError):
            H.run_with_transport_retry({}, "prompt", {})
        caller.assert_called_once()


class MatcherAndMetricTest(unittest.TestCase):
    def test_matcher_sets_are_exactly_disjoint(self):
        config = H.load_json(H.DATA_FILES["substitutes.json"])
        listed = {pattern for rows in config["listed"].values() for pattern in rows}
        substitute = {pattern for rows in config["substitute"].values() for pattern in rows}
        self.assertFalse(listed & substitute)

    def test_overlap_uses_first_catalog_id(self):
        hits = H.matcher_hits("You're absolutely right. In summary, stop.", "listed")
        self.assertEqual([row["pattern_id"] for row in hits], ["U01", "U02"])

    def test_contract_cap_uses_lexical_tokens(self):
        self.assertEqual(H.count_lexical("one two-three don't"), 3)
        self.assertEqual(H.count_lexical(" ".join(["rule"] * 60)), 60)
        self.assertEqual(H.count_lexical(" ".join(["rule"] * 61)), 61)

    def test_zero_density_rule_is_defined(self):
        self.assertEqual(H.coverage_per_100_contract_tokens(set(), 0), 0)
        self.assertEqual(H.coverage_per_100_contract_tokens({"U01"}, 20), 5)

    def test_sample_variance_is_n_minus_one(self):
        stats = H.mean_variance([1, 2, 3, 4, 5])
        self.assertEqual(stats["sample_variance"], 2.5)
        self.assertEqual(stats["sample_stdev"], 2.5 ** 0.5)

    def test_no_suppression_removes_preference_mapped_rule(self):
        interview = {"result": {"contract": "- Do not flatter.\n- Keep scope fixed.\n", "rules": [
            {"text": "Do not flatter.", "evidence_ids": ["O02"], "catalog_ids": ["U01"]},
            {"text": "Keep scope fixed.", "evidence_ids": ["I03"], "catalog_ids": []},
        ]}}
        rendered = H.suppression_contract(interview, "no_suppression")
        self.assertNotIn("Do not flatter", rendered)
        self.assertIn("Keep scope fixed", rendered)

    def test_density_uses_rendered_rule_sources_not_selected_fields(self):
        interview = {"result": {
            "selected_evidence_ids": ["O02", "O05"],
            "selected_catalog_ids": ["U03"],
            "rules": [{"text": "State facts once.", "evidence_ids": ["O02"], "catalog_ids": ["U03"]}],
        }}
        self.assertEqual(H.rendered_catalog_ids(interview), {"U03", "U05", "U06"})
        self.assertNotIn("U01", H.rendered_catalog_ids(interview))

    def test_density_counts_only_selected_relevant_rules(self):
        interview = {"result": {"rules": [
            {"catalog_ids": ["U01", "U03"], "evidence_ids": []},
        ]}}
        relevant = {"U01", "U03", "U05", "U06"}
        self.assertEqual(
            H.rendered_selected_relevant(interview, {"U01"}, relevant, True), {"U01"}
        )
        self.assertEqual(
            H.rendered_selected_relevant(interview, {"U01"}, relevant, False), set()
        )

    def test_undefined_rates_stay_out_of_pooled_totals(self):
        records = [
            {"substitute_hits": None, "output_tokens": 10},
            {"substitute_hits": 2, "output_tokens": 0},
        ]
        self.assertEqual(H.pooled_rate(records, "substitute_hits", "output_tokens"),
                         {"hits": 0, "tokens": 0, "rate_per_1000": None})
        self.assertEqual(H.stats_n(None), 0)

    def test_claim_screen_distinguishes_failure_incomplete_and_not_testable(self):
        self.assertEqual(H.screen_status(True, True), "pass")
        self.assertEqual(H.screen_status(True, False), "fail")
        self.assertEqual(H.screen_status(False, True), "incomplete")
        self.assertEqual(H.screen_status(True, True, not_testable=True), "not_testable")

    def test_task_success_is_derived_from_rows(self):
        self.assertTrue(H.derived_task_success({"status": "ok", "result": {
            "required_pass": [True, True], "fatal_hits": [False]
        }}))
        self.assertFalse(H.derived_task_success({"status": "ok", "result": {
            "required_pass": [True, False], "fatal_hits": [False]
        }}))

    def test_missing_task_outputs_and_judgments_are_incomplete(self):
        missing_judgment = {"status": "ok", "result": "missing", "task_id": "T01"}
        bad_judgment = {"status": "ok", "result": "bad", "task_id": "T02"}
        good_judgment = {"status": "ok", "result": "good", "task_id": "T03"}
        judgments = {
            H.digest({"text": "bad", "task": "T02"}): {"status": "error"},
            H.digest({"text": "good", "task": "T03"}): {
                "status": "ok", "result": {"required_pass": [True], "fatal_hits": []}
            },
        }
        rows = [None, {"status": "error"}, missing_judgment, bad_judgment, good_judgment]
        self.assertEqual(H.task_judge_error_count(rows, judgments), 4)


class RunnerSafetyTest(unittest.TestCase):
    def write_valid_reader_smoke(self, namespace, profile_name="haiku-reader"):
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["smoke"]["case"]
        payload = {
            "case_id": case["id"],
            "answers": [{**row, "sublabel": None} for row in case["expected"]],
        }
        assertions = H.grade_case(case, payload)
        _, key = H.cold_reader_namespace("smoke", profile_name)
        timestamp = "2026-08-24T00:00:00+00:00"
        profile = H.profile_map()[profile_name]
        record = {
            "profile": profile_name,
            "tier": "smoke",
            "rep": 1,
            "case_id": case["id"],
            "started_at": timestamp,
            "key": key,
            "status": "pass",
            "payload": payload,
            "assertions": assertions,
            "model": {
                "requested_model": profile["model"],
                "reported_models": [profile["reported_identity_required"]],
                "reported_providers": [profile["reported_provider_required"]],
            },
            "attempts": [{"attempt": 1, "status": "ok", "elapsed_seconds": 0}],
        }
        H.write_json_atomic(
            namespace / profile_name / "rep-1" / f"{case['id']}.json", record
        )
        H.write_json_atomic(namespace / "summary.json", {
            "type": "cold_reader",
            "tier": "smoke",
            "profile": profile_name,
            "key": key,
            "started_calls": 1,
            "passed": True,
            "assertions": len(assertions),
            "failed_assertions": 0,
            "errors": 0,
            "completed_at": timestamp,
        })

    def write_valid_adapter_smoke(self, namespace):
        profiles = H.profile_map()
        case = H.load_json(H.DATA_FILES["cold_reader_cases.json"])["smoke"]["case"]
        payload = {
            "case_id": case["id"],
            "answers": [{**row, "sublabel": None} for row in case["expected"]],
        }

        def metadata(name):
            profile = profiles[name]
            value = {
                "requested_model": profile["model"],
                "reported_models": ([profile["reported_identity_required"]]
                                    if profile.get("reported_identity_required") else []),
                "reported_providers": ([profile["reported_provider_required"]]
                                       if profile.get("reported_provider_required") else []),
            }
            if profile["adapter"] == "codex_cli":
                value.update({
                    "identity_evidence": profile["identity_evidence"],
                    "cli_version": "codex-cli test",
                })
            return value

        def record(name, probe, result):
            return {
                "kind": "adapter_smoke",
                "profile": name,
                "path": probe,
                "status": "ok",
                "result": result,
                "model": metadata(name),
                "attempts": [{"attempt": 1, "status": "ok", "elapsed_seconds": 0}],
            }

        for name in ("fable-subject", "kimi-subject"):
            H.write_json_atomic(namespace / name / "tool.json", record(
                name, "tool", {"payload": payload, "assertions": H.grade_case(case, payload)}
            ))
            H.write_json_atomic(namespace / name / "text.json", record(name, "text", "SMOKE_OK"))
        judge = H.load_json(H.DATA_FILES["models.json"])["judge_profile"]
        H.write_json_atomic(namespace / judge / "task-schema.json", record(
            judge, "task_schema",
            {"task_id": "SMOKE", "required_pass": [True, True], "fatal_hits": [False]},
        ))
        H.write_json_atomic(namespace / judge / "substitute-schema.json", record(
            judge, "substitute_schema",
            {"verdicts": [
                {"candidate_id": "c1", "pattern_id": None},
                {"candidate_id": "c2", "pattern_id": "U01"},
            ]},
        ))
        _, key = H.adapter_smoke_namespace()
        H.write_json_atomic(namespace / "summary.json", {
            "type": "adapter_smoke",
            "key": key,
            "passed": True,
            "calls": 6,
            "errors": 0,
            "completed_at": "2026-08-24T00:00:00+00:00",
        })

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        with self.assertRaisesRegex(H.HarnessError, "duplicate JSON object key"):
            H.strict_json_loads('{"value":1,"value":2}')
        with self.assertRaisesRegex(H.HarnessError, "non-finite JSON number"):
            H.strict_json_loads('{"value":NaN}')
        with self.assertRaisesRegex(H.HarnessError, "non-finite JSON number"):
            H.strict_json_loads('{"value":1e999}')

    def test_schedule_has_five_per_arm_and_family(self):
        schedule = H.measured_schedule()
        self.assertEqual(len(schedule), 20)
        seen = {(row["family"], row["arm"], row["rep"]) for row in schedule}
        self.assertEqual(len(seen), 20)
        for family in ("fable-subject", "kimi-subject"):
            for arm in ("control", "treatment"):
                self.assertEqual(sum(row["family"] == family and row["arm"] == arm for row in schedule), 5)

    def test_model_registry_has_no_command_fragments_or_fallback(self):
        models = H.load_json(H.DATA_FILES["models.json"])
        text = H.canonical(models)
        self.assertNotIn('"command"', text)
        self.assertNotIn("fallback", text.lower())
        self.assertEqual(models["profiles"]["haiku-reader"]["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(models["profiles"]["haiku-reader"]["effort"], "low")
        deepseek = models["profiles"]["deepseek-reader"]
        self.assertEqual(deepseek["adapter"], "deepinfra_api")
        self.assertEqual(deepseek["api_base"], "https://api.deepinfra.com/v1/openai")
        self.assertEqual(deepseek["model"], "deepseek-ai/DeepSeek-V4-Flash-0731")
        self.assertEqual(deepseek["credential_env"], "DEEPINFRA_API_KEY")
        self.assertNotIn("thinking", deepseek)

    def test_cold_reader_attempt_key_binds_profile_and_harness(self):
        namespace, key = H.cold_reader_namespace("smoke", "deepseek-reader")
        profile = H.load_json(H.DATA_FILES["models.json"])["profiles"]["deepseek-reader"]
        self.assertEqual(key["profile_sha256"], H.sha256_value(profile))
        self.assertEqual(key["harness_sha256"], H.sha256(H.E09 / "harness.py"))
        self.assertEqual(key["catalog_sha256"], H.sha256_text(H.smoke_catalog_markdown()))
        self.assertNotEqual(key["catalog_sha256"], H.sha256(H.DATA_FILES["catalog.json"]))
        _, qualification_key = H.cold_reader_namespace("qualification", "deepseek-reader")
        self.assertEqual(qualification_key["catalog_sha256"], H.sha256(H.DATA_FILES["catalog.json"]))
        self.assertTrue(namespace.name.startswith("cr-"))

    def test_harness_qualification_row_round_trips_through_trusted_verifier(self):
        suite = H.load_json(H.DATA_FILES["cold_reader_cases.json"])
        namespace, key = H.cold_reader_namespace("qualification", "haiku-reader")
        assertions_per_rep = 0
        for case in suite["qualification"]["cases"]:
            payload = {"case_id": case["id"]}
            if case["kind"] == "semantics":
                payload.update(case["expected"])
            else:
                payload["answers"] = case["expected"]
            assertions_per_rep += len(H.grade_case(case, payload))
        repetitions = suite["qualification"]["repetitions_per_profile"]
        summary = {
            "profile": "haiku-reader",
            "tier": "qualification",
            "passed": True,
            "started_calls": len(suite["qualification"]["cases"]) * repetitions,
            "assertions": assertions_per_rep * repetitions,
            "failed_assertions": 0,
            "errors": 0,
            "key": key,
            "completed_at": "2026-08-24T00:00:00+00:00",
        }
        row = H.cold_reader_ledger_line(summary, namespace)
        H.artifact_store.validate_cold_reader_qualification_row(row, H.ROOT)

    def test_measured_gate_regrades_complete_qualification_evidence(self):
        old_raw = H.RAW
        with tempfile.TemporaryDirectory(dir=H.ROOT) as name:
            try:
                H.RAW = Path(name) / "raw"
                suite = H.load_json(H.DATA_FILES["cold_reader_cases.json"])
                namespace, key = H.cold_reader_namespace("qualification", "haiku-reader")
                timestamp = "2026-08-24T00:00:00+00:00"
                H.write_json_atomic(namespace / "attempt.json", {
                    "status": "started", "started_at": timestamp, "key": key,
                })
                records = []
                for rep in range(1, suite["qualification"]["repetitions_per_profile"] + 1):
                    for case in suite["qualification"]["cases"]:
                        payload = {"case_id": case["id"]}
                        if case["kind"] == "semantics":
                            payload.update(case["expected"])
                        else:
                            payload["answers"] = case["expected"]
                        assertions = H.grade_case(case, payload)
                        record = {
                            "profile": "haiku-reader",
                            "tier": "qualification",
                            "rep": rep,
                            "case_id": case["id"],
                            "started_at": timestamp,
                            "key": key,
                            "status": "pass",
                            "payload": payload,
                            "assertions": assertions,
                            "model": {
                                "requested_model": "claude-haiku-4-5-20251001",
                                "reported_models": ["claude-haiku-4-5-20251001"],
                                "reported_providers": ["firstParty"],
                            },
                            "attempts": [{"attempt": 1, "status": "ok", "elapsed_seconds": 0}],
                        }
                        H.write_json_atomic(
                            namespace / "haiku-reader" / f"rep-{rep}" / f"{case['id']}.json",
                            record,
                        )
                        records.append(record)
                summary = {
                    "type": "cold_reader",
                    "tier": "qualification",
                    "profile": "haiku-reader",
                    "key": key,
                    "started_calls": len(records),
                    "passed": True,
                    "assertions": sum(len(record["assertions"]) for record in records),
                    "failed_assertions": 0,
                    "errors": 0,
                    "completed_at": timestamp,
                }
                line = H.cold_reader_ledger_line(summary, namespace)
                summary["ledger_run_id"] = line["run_id"]
                H.write_json_atomic(namespace / "summary.json", summary)
                self.assertEqual(
                    H.validate_qualification_evidence(summary, namespace, "haiku-reader"), line
                )
                first = namespace / "haiku-reader" / "rep-1" / "C0.json"
                changed = H.load_json(first)
                changed["payload"]["automatic_bans"] = True
                H.write_json_atomic(first, changed)
                with self.assertRaisesRegex(H.HarnessError, "assertions differ"):
                    H.validate_qualification_evidence(summary, namespace, "haiku-reader")
                changed["assertions"] = H.grade_case(
                    suite["qualification"]["cases"][0], changed["payload"]
                )
                changed["status"] = "fail"
                H.write_json_atomic(first, changed)
                failed_summary = {
                    **summary,
                    "passed": False,
                    "failed_assertions": 1,
                }
                failed_payload = {
                    key: value for key, value in failed_summary.items() if key != "ledger_run_id"
                }
                failed_line = H.cold_reader_ledger_line(failed_payload, namespace)
                failed_summary["ledger_run_id"] = failed_line["run_id"]
                H.write_json_atomic(namespace / "summary.json", failed_summary)
                self.assertEqual(
                    H.validate_qualification_evidence(
                        failed_summary, namespace, "haiku-reader"
                    ),
                    failed_line,
                )
                with self.assertRaisesRegex(H.HarnessError, "has not passed"):
                    H.validate_qualification_evidence(
                        failed_summary, namespace, "haiku-reader", require_pass=True
                    )
            finally:
                H.RAW = old_raw

    def test_harness_result_identity_round_trips_through_trusted_verifier(self):
        from experiments.test_artifacts import e09_manifest, e09_result_row

        expected = e09_result_row()
        payload = {key: value for key, value in expected.items() if key not in ("run_id", "date")}
        row = H.measured_result_ledger_line(payload, expected["completed_at"])
        self.assertEqual(row, expected)
        H.artifact_store.validate_e09_result_row(row, e09_manifest())

    def test_smoke_attempts_are_repeatable_and_latest_selection_does_not_read_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "smoke"
            self.assertEqual(H.next_smoke_attempt(base).name, "attempt-001")
            first = base / "attempt-001"
            first.mkdir(parents=True)
            H.write_json_atomic(first / "summary.json", {"passed": False})
            self.assertEqual(H.next_smoke_attempt(base).name, "attempt-002")
            second = base / "attempt-002"
            second.mkdir()
            H.write_json_atomic(second / "summary.json", {"passed": True})
            self.assertEqual(H.latest_smoke_attempt(base), second)
            third = base / "attempt-003"
            third.mkdir()
            H.write_json_atomic(third / "summary.json", {"passed": False})
            self.assertEqual(H.latest_smoke_attempt(base), third)

    def test_adapter_smoke_gate_revalidates_records_not_summary_claims(self):
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            namespace = Path(tmp) / "attempt-001"
            self.write_valid_adapter_smoke(namespace)
            self.assertTrue(H.validate_adapter_smoke_evidence(namespace)["passed"])
            summary = H.load_json(namespace / "summary.json")
            summary["calls"] = 1
            H.write_json_atomic(namespace / "summary.json", summary)
            with self.assertRaisesRegex(H.HarnessError, "summary differs"):
                H.validate_adapter_smoke_evidence(namespace)
            summary["calls"] = 6.0
            H.write_json_atomic(namespace / "summary.json", summary)
            with self.assertRaisesRegex(H.HarnessError, "summary differs"):
                H.validate_adapter_smoke_evidence(namespace)

    def test_reader_smoke_gate_validates_namespace_before_summary(self):
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            namespace = Path(tmp) / "attempt-001"
            self.write_valid_reader_smoke(namespace)
            self.assertTrue(H.validate_reader_smoke_evidence(
                namespace, "haiku-reader", require_pass=True
            )["passed"])
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            summary = namespace / "summary.json"
            summary.unlink()
            summary.symlink_to(outside)
            with self.assertRaisesRegex(H.HarnessError, "symlink"):
                H.validate_reader_smoke_evidence(
                    namespace, "haiku-reader", require_pass=True
                )

    def test_qualification_namespace_rejects_redirected_parent(self):
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            base = Path(tmp)
            real = base / "real"
            namespace = real / "qualification"
            namespace.mkdir(parents=True)
            linked_parent = base / "redirected"
            linked_parent.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(H.HarnessError, "redirected parent"):
                H.validate_qualification_evidence(
                    {}, linked_parent / "qualification", "haiku-reader"
                )

    def test_new_qualification_namespace_rejects_redirected_parent(self):
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            base = Path(tmp)
            real = base / "real"
            real.mkdir()
            linked_parent = base / "redirected"
            linked_parent.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(H.HarnessError, "symlink"):
                H.ensure_local_namespace(
                    linked_parent / "qualification", "qualification evidence"
                )
            self.assertFalse((real / "qualification").exists())

    def test_partial_qualification_namespace_stops_before_any_call(self):
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            namespace = Path(tmp) / "qualification"
            namespace.mkdir()
            self.assertIsNone(H.validated_qualification_summary(
                namespace, "haiku-reader", allow_empty=True
            ))
            H.write_json_atomic(namespace / "haiku-reader" / "rep-1" / "C0.json", {})
            with self.assertRaisesRegex(H.HarnessError, "namespace is incomplete"):
                H.validated_qualification_summary(
                    namespace, "haiku-reader", allow_empty=True
                )

    def test_dotenv_parser_never_evaluates_shell_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("SAFE='$(touch should-not-exist)'\n", encoding="utf-8")
            self.assertEqual(H.read_dotenv(path)["SAFE"], "$(touch should-not-exist)")
            self.assertFalse((Path(tmp) / "should-not-exist").exists())

    def test_append_jsonl_refuses_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            path.write_text("", encoding="utf-8")
            H.append_jsonl(path, {"run_id": "r-1", "value": 1})
            with self.assertRaises(H.HarnessError):
                H.append_jsonl(path, {"run_id": "r-1", "value": 2})

    def test_append_jsonl_compares_run_id_fields_not_substrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            H.append_jsonl(path, {"run_id": "r-2", "note": "mentions r-1"})
            H.append_jsonl(path, {"run_id": "r-1", "value": 2})
            rows = [json.loads(raw) for raw in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["run_id"] for row in rows], ["r-2", "r-1"])

    def test_append_jsonl_requires_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            with self.assertRaisesRegex(H.HarnessError, "non-empty string run_id"):
                H.append_jsonl(path, {"value": 1})

    def test_append_jsonl_rejects_existing_row_without_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            path.write_text('{"value": 1}\n', encoding="utf-8")
            with self.assertRaisesRegex(H.HarnessError, "non-empty string run_id"):
                H.append_jsonl(path, {"run_id": "r-1"})

    def test_measured_gate_requires_current_qualification_ledger_additions(self):
        diff = "\n".join([
            "diff --git a/ledger/runs.jsonl b/ledger/runs.jsonl",
            "--- a/ledger/runs.jsonl",
            "+++ b/ledger/runs.jsonl",
            "@@ -1,0 +2 @@",
            '+{"run_id":"qualification-one"}',
        ])
        completed = mock.Mock(returncode=0, stdout=diff)
        with mock.patch.object(H.subprocess, "run", return_value=completed):
            self.assertTrue(H.ledger_diff_contains_only(
                ["qualification-one"], required_run_ids=["qualification-one"]
            ))
            self.assertFalse(H.ledger_diff_contains_only(
                ["qualification-one", "qualification-two"],
                required_run_ids=["qualification-one", "qualification-two"],
            ))
        committed_only = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(H.subprocess, "run", return_value=committed_only):
            self.assertFalse(H.ledger_diff_contains_only(
                ["qualification-one"], required_run_ids=["qualification-one"]
            ))

    def test_host_metadata_sanitizer_removes_paths_and_session_identifiers(self):
        raw = {
            "executable": "/Users/alice/bin/codex",
            "session_id": "session-secret",
            "nested": {
                "cwd": "/tmp/e09-tool-secret",
                "plugins": [{"path": "/Users/alice/.claude/plugins/example"}],
                "thread_id": "thread-secret",
                "stderr_tail": "failed under /home/alice/private/file.txt",
                "stdout": (
                    'session_id=79125914-c30f-4203-a6ab-f4b6ccb57f67 '
                    '{\\"project\\":\\"e09-tool-nmxf38t6\\"}'
                ),
                "secret_text": "DEEPINFRA_API_KEY=local-secret Authorization: Bearer sk-test.value",
                "apiKeySource": "none",
                "keep": "reported-model",
            },
            "api_key": "local-secret",
        }
        self.assertEqual(H.sanitize_host_metadata(raw), {
            "executable": "codex",
            "nested": {
                "stderr_tail": "failed under <HOST_PATH>",
                "stdout": 'session_id=<ID> {\\"project\\":\\"<PROJECT_ID>\\"}',
                "secret_text": "DEEPINFRA_API_KEY=<SECRET> Authorization: Bearer <SECRET>",
                "apiKeySource": "none",
                "keep": "reported-model",
            },
        })

    def test_committed_smoke_artifacts_have_portable_metadata(self):
        dotenv = H.read_dotenv(H.ROOT / ".env")
        credential_names = {
            profile.get("credential_env")
            for profile in H.profile_map().values()
            if profile.get("credential_env")
        }
        credential_names.update(
            name for name in dotenv
            if name.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
        )
        credential_names.update(
            name for name in os.environ
            if name.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
        )
        local_secrets = {
            value
            for name in credential_names
            for value in (os.environ.get(name), dotenv.get(name))
            if value and len(value) >= 8
        }
        for path in (H.RAW / "smoke").rglob("*.json"):
            payload = H.load_json(path)
            self.assertEqual(payload, H.sanitize_host_metadata(payload), str(path))
            text = H.canonical(payload)
            self.assertNotIn("DEEPSEEK_API_KEY", text, str(path))
            self.assertFalse(any(secret in text for secret in local_secrets), str(path))

    def test_exclusive_json_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attempt.json"
            H.write_json_exclusive(path, {"status": "started"})
            with self.assertRaises(H.HarnessError):
                H.write_json_exclusive(path, {"status": "restarted"})

    def test_final_ledger_ensure_is_idempotent_and_collision_safe(self):
        old_ledger = H.LEDGER
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.LEDGER = Path(tmp) / "runs.jsonl"
                line = {"run_id": "r-stable", "value": 1}
                H.ensure_ledger_lines([line])
                H.ensure_ledger_lines([line])
                self.assertEqual(H.LEDGER.read_text().splitlines(), [H.canonical(line)])
                with self.assertRaises(H.HarnessError):
                    H.ensure_ledger_lines([{"run_id": "r-stable", "value": 2}])
            finally:
                H.LEDGER = old_ledger

    def test_qualification_summary_ledger_reconciles_both_crash_windows(self):
        old_root = H.ROOT
        old_ledger = H.LEDGER
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.ROOT = Path(tmp)
                H.LEDGER = H.ROOT / "ledger" / "runs.jsonl"
                summary = {
                    "type": "cold_reader",
                    "tier": "qualification",
                    "profile": "haiku-reader",
                    "key": {"freeze_sha256": "freeze"},
                    "started_calls": 5,
                    "passed": True,
                    "assertions": 30,
                    "failed_assertions": 0,
                    "errors": 0,
                    "completed_at": "2026-08-21T12:00:00+00:00",
                }

                ledger_first = H.ROOT / "raw" / "qualification" / "cr-ledger-first"
                ledger_first_path = ledger_first / "summary.json"
                line = H.cold_reader_ledger_line(summary, ledger_first)
                self.assertEqual((line["experiment"], line["tier"]), ("E-09-cold-reader", "qualification"))
                H.ensure_ledger_lines([line])
                H.write_json_atomic(ledger_first_path, summary)
                repaired = H.ensure_qualification_summary_ledger(
                    ledger_first_path, H.load_json(ledger_first_path), ledger_first
                )
                self.assertEqual(repaired["ledger_run_id"], line["run_id"])
                self.assertEqual(H.load_json(ledger_first_path)["ledger_run_id"], line["run_id"])

                summary_first = H.ROOT / "raw" / "qualification" / "cr-summary-first"
                summary_first_path = summary_first / "summary.json"
                line = H.cold_reader_ledger_line(summary, summary_first)
                H.write_json_atomic(summary_first_path, {**summary, "ledger_run_id": line["run_id"]})
                repaired = H.ensure_qualification_summary_ledger(
                    summary_first_path, H.load_json(summary_first_path), summary_first
                )
                self.assertEqual(repaired["ledger_run_id"], line["run_id"])
                self.assertIn(line["run_id"], H.jsonl_run_ids(H.LEDGER))
                self.assertTrue(line["run_id"].startswith("r-20260821-"))
            finally:
                H.ROOT = old_root
                H.LEDGER = old_ledger

    def test_measured_manifest_detects_delete_or_mutation(self):
        old_raw = H.RAW
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.RAW = Path(tmp) / "raw"
                namespace = H.RAW / "measured" / "m-test"
                path = namespace / "interviews" / "one.json"
                H.start_measured_record(path)
                H.write_json_atomic(path, {"status": "ok"})
                H.complete_measured_record(path)
                H.verify_measured_record(path)
                H.write_json_atomic(path, {"status": "changed"})
                with self.assertRaises(H.HarnessError):
                    H.verify_measured_record(path)
            finally:
                H.RAW = old_raw

    def test_measured_manifest_recovers_both_append_crash_windows_without_repeating_call(self):
        old_raw = H.RAW
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.RAW = Path(tmp) / "raw"
                namespace = H.RAW / "measured" / "m-test"
                missing = namespace / "interviews" / "missing.json"
                H.start_measured_record(missing)
                provider = mock.Mock(side_effect=AssertionError("provider must not run"))
                interrupted = H.call_record(
                    missing, provider, {"kind": "interview", "rep": 1}
                )
                self.assertEqual(interrupted["status"], "interrupted")
                provider.assert_not_called()
                H.validate_attempt_protocol(interrupted, "interviews/missing.json")
                H.verify_measured_record(missing)

                written = namespace / "interviews" / "written.json"
                H.start_measured_record(written)
                H.write_json_atomic(written, {"kind": "interview", "status": "ok"})
                provider = mock.Mock(side_effect=AssertionError("provider must not run"))
                recovered = H.call_record(
                    written, provider, {"kind": "interview", "rep": 2}
                )
                self.assertEqual(recovered["status"], "ok")
                provider.assert_not_called()
                H.verify_measured_record(written)
            finally:
                H.RAW = old_raw

    def test_measured_manifest_rejects_paths_outside_its_namespace(self):
        old_raw = H.RAW
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.RAW = Path(tmp) / "raw"
                namespace = H.RAW / "measured" / "m-test"
                namespace.mkdir(parents=True)
                for unsafe in ("../outside.json", "/tmp/outside.json", r"interviews\outside.json"):
                    with mock.patch.object(H, "measured_manifest_rows", return_value=[{"path": unsafe}]), \
                         self.assertRaisesRegex(H.HarnessError, "unsafe path"):
                        H.verify_measured_manifest(namespace)
            finally:
                H.RAW = old_raw

    def test_measured_manifest_rejects_linked_records_inside_its_namespace(self):
        old_raw = H.RAW
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.RAW = Path(tmp) / "raw"
                namespace = H.RAW / "measured" / "m-test"
                records = namespace / "interviews"
                records.mkdir(parents=True)
                outside = Path(tmp) / "outside.json"
                outside.write_text("{}\n", encoding="utf-8")
                linked = records / "linked.json"
                linked.symlink_to(outside)
                with mock.patch.object(H, "measured_manifest_rows", return_value=[{
                    "path": "interviews/linked.json",
                }]), self.assertRaisesRegex(H.HarnessError, "contains a symlink"):
                    H.verify_measured_manifest(namespace)
                linked.unlink()
                os.link(outside, linked)
                with mock.patch.object(H, "measured_manifest_rows", return_value=[{
                    "path": "interviews/linked.json",
                }]), self.assertRaisesRegex(H.HarnessError, "unsafe path"):
                    H.verify_measured_manifest(namespace)
            finally:
                H.RAW = old_raw

    def test_freeze_excludes_run_outputs(self):
        frozen = set(H.freeze_payload()["files"])
        self.assertTrue(frozen)
        self.assertFalse(any("/raw/" in path for path in frozen))
        self.assertNotIn("ledger/runs.jsonl", frozen)

    def test_artifact_inventory_derives_all_planned_interviews_and_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = H.artifact_expected_paths(Path(tmp), [{"status": "excluded"}] * 120)
        interviews = [path for path in expected if path.startswith("interviews/")]
        tasks = [path for path in expected if path.startswith("tasks/")]
        self.assertEqual(len(interviews), 20)
        self.assertEqual(len(tasks), 120)
        self.assertIn("metadata.json", expected)
        self.assertIn("record-manifest.jsonl", expected)

    def test_adjudication_files_exist_only_for_derived_disagreements(self):
        with tempfile.TemporaryDirectory() as tmp:
            namespace = Path(tmp)
            H.write_json_atomic(namespace / "adjudication-pending.json", {})
            with mock.patch.object(H, "iter_records", return_value=[]), \
                 self.assertRaisesRegex(H.HarnessError, "without substitute-judge disagreements"):
                H.load_substitute_verdicts(namespace, [])
            H.write_json_atomic(namespace / "adjudication-resolved.json", {})
            expected = H.artifact_expected_paths(namespace, [], adjudication_required=True)
            self.assertIn("adjudication-pending.json", expected)
            self.assertIn("adjudication-resolved.json", expected)

    def test_stale_or_partial_adjudication_state_stops_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            namespace = Path(tmp)
            with self.assertRaisesRegex(H.HarnessError, "require both adjudication records"):
                H.artifact_expected_paths(namespace, [], adjudication_required=True)
            H.write_json_atomic(namespace / "adjudication-resolved.json", {"resolutions": []})
            task = {"status": "ok", "result": "candidate response", "task_id": "T01"}
            blind = H.digest({"text": task["result"], "task": task["task_id"]})
            judgments = [
                {"blind_id": blind, "pass": 1, "status": "ok", "result": {"verdicts": []}},
                {"blind_id": blind, "pass": 2, "status": "ok", "result": {
                    "verdicts": [{"different": True}],
                }},
            ]
            with mock.patch.object(H, "iter_records", return_value=judgments), \
                 mock.patch.object(H, "matcher_hits", return_value=[{"text": "candidate"}]), \
                 mock.patch.object(H, "build_adjudication_pending", return_value={"current": True}), \
                 self.assertRaisesRegex(H.HarnessError, "without its pending record"):
                H.load_substitute_verdicts(namespace, [task])
            (namespace / "adjudication-resolved.json").unlink()
            H.write_json_atomic(namespace / "adjudication-pending.json", {"stale": True})
            with mock.patch.object(H, "iter_records", return_value=judgments), \
                 mock.patch.object(H, "matcher_hits", return_value=[{"text": "candidate"}]), \
                 mock.patch.object(H, "build_adjudication_pending", return_value={"current": True}), \
                 self.assertRaisesRegex(H.HarnessError, "differs from current disagreements"):
                H.load_substitute_verdicts(namespace, [task])

    def test_artifact_records_bind_embedded_identity_to_path(self):
        record = {"kind": "task", "family": "fable-subject", "arm": "control", "rep": 1}
        H.validate_record_identity(record, record.copy(), "tasks/example.json")
        with self.assertRaisesRegex(H.HarnessError, "identity differs from path"):
            H.validate_record_identity(record, {**record, "rep": 2}, "tasks/example.json")
        with self.assertRaisesRegex(H.HarnessError, "identity differs from path"):
            H.validate_record_identity({**record, "rep": True}, record, "tasks/example.json")
        job = H.measured_schedule()[0]
        interview = {"kind": "interview", **job}
        H.validate_record_identity(interview, {"kind": "interview", **job}, "interviews/example.json")

    def test_successful_artifact_payloads_must_match_frozen_schemas(self):
        valid = {"status": "ok", "result": "task output"}
        H.validate_success_schema(valid, {"type": "string", "minLength": 1}, "tasks/T01.json")
        with self.assertRaisesRegex(H.HarnessError, "frozen schema"):
            H.validate_success_schema(
                {"status": "ok", "result": {}}, H.contract_schema("control"), "interviews/rep-1.json"
            )
        task = H.load_json(H.DATA_FILES["tasks.json"])["tasks"][0]
        schema = H.task_judge_schema(
            task["id"], len(task["rubric"]["required"]), len(task["rubric"]["fatal"])
        )
        with self.assertRaisesRegex(H.HarnessError, "frozen schema"):
            H.validate_success_schema({"status": "ok", "result": {}}, schema, "judgments/task/x.json")

    def test_interview_derived_fields_are_recomputed_from_successful_payload(self):
        record = {
            "status": "ok",
            "result": {"contract": "Lead with the outcome."},
            "contract_lexical_tokens": 999,
            "over_cap": False,
            "contract_violations": [],
        }
        with mock.patch.object(H, "contract_violations", return_value=[]):
            with self.assertRaisesRegex(H.HarnessError, "derived fields differ"):
                H.validate_interview_derived_fields(record, "control", "interviews/rep-1.json")

    def test_substitute_blind_requires_a_matching_successful_task(self):
        task = {"status": "ok", "result": "candidate", "task_id": "T01"}
        blind = H.digest({"text": task["result"], "task": task["task_id"]})
        self.assertEqual(H.successful_task_for_blind([task], blind), task)
        with self.assertRaisesRegex(H.HarnessError, "no matching successful task"):
            H.successful_task_for_blind([task], "missing")

    def test_artifact_attempts_follow_the_exact_retry_protocol(self):
        H.validate_attempt_protocol({
            "kind": "task", "status": "ok", "result": "done",
            "attempts": [{"attempt": 1, "status": "ok", "elapsed_seconds": 0.1}],
        }, "tasks/ok.json")
        H.validate_attempt_protocol({
            "kind": "task", "status": "transport_error", "error": "offline",
            "attempts": [
                {"attempt": 1, "status": "transport_error", "error": "offline", "elapsed_seconds": 0.1},
                {"attempt": 2, "status": "transport_error", "error": "offline", "elapsed_seconds": 0.1},
            ],
        }, "tasks/error.json")
        with self.assertRaisesRegex(H.HarnessError, "retry protocol"):
            H.validate_attempt_protocol({
                "kind": "task", "status": "ok", "result": "done",
                "attempts": [
                    {"attempt": 1, "status": "ok", "elapsed_seconds": 0.1},
                    {"attempt": 2, "status": "ok", "elapsed_seconds": 0.1},
                ],
            }, "tasks/bad.json")
        with self.assertRaisesRegex(H.HarnessError, "non-empty reason"):
            H.validate_attempt_protocol({"kind": "task", "status": "excluded"}, "tasks/excluded.json")
        with self.assertRaisesRegex(H.HarnessError, "elapsed_seconds"):
            H.validate_attempt_protocol({
                "kind": "task", "status": "ok", "result": "done",
                "attempts": [{"attempt": 1, "status": "ok", "elapsed_seconds": float("nan")}],
            }, "tasks/nan.json")
        with self.assertRaisesRegex(H.HarnessError, "must not carry a result"):
            H.validate_attempt_protocol({
                "kind": "task", "status": "request_error", "error": "bad request", "result": "fabricated",
                "attempts": [{
                    "attempt": 1, "status": "request_error", "error": "bad request", "elapsed_seconds": 0.1,
                }],
            }, "tasks/failed-result.json")
        with self.assertRaisesRegex(H.HarnessError, "must not carry a result"):
            H.validate_attempt_protocol({
                "kind": "task", "status": "excluded", "reason": "not scheduled", "result": "fabricated",
            }, "tasks/excluded-result.json")

    def test_artifact_schedules_are_rederived_from_frozen_records(self):
        interviews = [{**job, "kind": "interview"} for job in H.measured_schedule()]
        tasks = [{"status": "excluded"}] * 120
        metadata = {
            "task_schedule": H.measured_task_schedule(interviews),
            "judge_schedule": H.measured_judge_schedule(tasks),
        }
        self.assertEqual(len(metadata["task_schedule"]), 120)
        H.validate_artifact_schedules(metadata, interviews, tasks)
        metadata["task_schedule"] = list(reversed(metadata["task_schedule"]))
        with self.assertRaisesRegex(H.HarnessError, "task schedule differs"):
            H.validate_artifact_schedules(metadata, interviews, tasks)

    def test_artifact_metadata_binds_experiment_freeze_commit_and_schedule(self):
        head = "a" * 40
        metadata = {
            "experiment": "E-09",
            "freeze_sha256": H.sha256(H.E09 / "freeze.json"),
            "base_commit": head,
            "started_at": "2026-08-24T00:00:00+00:00",
            "schedule": H.measured_schedule(),
        }
        H.validate_artifact_metadata(metadata, head)
        for field, value in (("experiment", "E-08"), ("freeze_sha256", "0" * 64)):
            changed = {**metadata, field: value}
            with self.assertRaises(H.HarnessError):
                H.validate_artifact_metadata(changed, head)

    def test_measured_namespace_rejects_missing_or_stale_metadata_before_reuse(self):
        head = "a" * 40
        with tempfile.TemporaryDirectory(dir=H.ROOT) as tmp:
            namespace = Path(tmp) / "measured"
            namespace.mkdir()
            self.assertIsNone(H.validate_existing_measured_metadata(namespace, head))
            H.write_json_atomic(namespace / "record-manifest.jsonl", {})
            with self.assertRaisesRegex(H.HarnessError, "missing metadata"):
                H.validate_existing_measured_metadata(namespace, head)
            (namespace / "record-manifest.jsonl").unlink()
            metadata = {
                "experiment": "E-09",
                "freeze_sha256": H.sha256(H.E09 / "freeze.json"),
                "base_commit": head,
                "started_at": "2026-08-24T00:00:00+00:00",
                "schedule": H.measured_schedule(),
            }
            H.write_json_atomic(namespace / "metadata.json", metadata)
            self.assertEqual(H.validate_existing_measured_metadata(namespace, head), metadata)
            metadata["base_commit"] = "b" * 40
            H.write_json_atomic(namespace / "metadata.json", metadata)
            with self.assertRaisesRegex(H.HarnessError, "differs from HEAD"):
                H.validate_existing_measured_metadata(namespace, head)

    def test_artifact_namespace_rejects_root_or_child_symlinks_before_reads(self):
        old_root = H.ROOT
        with tempfile.TemporaryDirectory() as name:
            try:
                H.ROOT = Path(name)
                real = H.ROOT / "real"
                real.mkdir()
                os.symlink(real, H.ROOT / "namespace")
                with self.assertRaisesRegex(H.HarnessError, "symlink"):
                    H.validate_artifact_namespace(H.ROOT / "namespace")
                (H.ROOT / "namespace").unlink()
                namespace = H.ROOT / "namespace"
                namespace.mkdir()
                target = H.ROOT / "outside.json"
                target.write_text("{}\n", encoding="utf-8")
                os.symlink(target, namespace / "linked.json")
                with self.assertRaisesRegex(H.HarnessError, "symlink"):
                    H.validate_artifact_namespace(namespace)
            finally:
                H.ROOT = old_root

    def test_measured_namespace_is_created_and_rejects_redirected_children_before_calls(self):
        old_root = H.ROOT
        with tempfile.TemporaryDirectory() as name:
            try:
                H.ROOT = Path(name)
                namespace = H.ROOT / "experiments" / "e09" / "raw" / "measured" / "m-test"
                H.ensure_measured_namespace(namespace)
                self.assertTrue(namespace.is_dir())
                outside = H.ROOT / "outside"
                outside.mkdir()
                os.symlink(outside, namespace / "interviews")
                with self.assertRaisesRegex(H.HarnessError, "symlink"):
                    H.ensure_measured_namespace(namespace)
            finally:
                H.ROOT = old_root

    def test_artifact_spec_cannot_redirect_e09_repository(self):
        original = H.DATA_FILES["artifact-spec.json"]
        with tempfile.TemporaryDirectory() as name:
            changed = H.load_json(original)
            changed["repository"] = {"id": 1, "name": "other/repo"}
            path = Path(name) / "artifact-spec.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            H.DATA_FILES["artifact-spec.json"] = path
            try:
                with self.assertRaisesRegex(H.HarnessError, "canonical E-09 repository"):
                    H.load_artifact_spec()
            finally:
                H.DATA_FILES["artifact-spec.json"] = original

    def test_e09_remote_verification_passes_canonical_repository(self):
        with mock.patch.object(H, "load_json", return_value={"manifest": True}), \
             mock.patch.object(H.artifact_store, "download_and_verify", return_value={"verified": True}) as remote:
            self.assertEqual(H.verify_published_artifact(Path("manifest.json")), {"verified": True})
        remote.assert_called_once_with(
            {"manifest": True}, Path("manifest.json"), expected_repository="mlamp/meta-skills"
        )

    def test_existing_compact_result_must_equal_recomputed_lines(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "result.json"
            completed = "2026-08-24T00:00:00+00:00"
            saved = {"schema_version": 2, "lines": [
                {"run_id": "r-one", "completed_at": completed},
                {"run_id": "r-two", "completed_at": completed},
            ]}
            H.write_json_atomic(path, saved)
            existing, timestamp = H.load_existing_compact_result(path)
            self.assertEqual(timestamp, completed)
            H.write_or_verify_compact_result(path, saved, existing)
            changed = {**saved, "lines": [{**saved["lines"][0], "fabricated": True}, saved["lines"][1]]}
            with self.assertRaisesRegex(H.HarnessError, "differs from recomputed"):
                H.write_or_verify_compact_result(path, changed, existing)
            saved["lines"][0]["completed_at"] = "not-a-time"
            saved["lines"][1]["completed_at"] = "not-a-time"
            H.write_json_atomic(path, saved)
            with self.assertRaisesRegex(H.HarnessError, "not ISO 8601"):
                H.load_existing_compact_result(path)

    def test_measured_operations_require_the_commit_that_last_changed_freeze(self):
        old_frozen_commit = H.frozen_commit
        try:
            H.frozen_commit = lambda: "a" * 40
            H.require_exact_frozen_head("a" * 40, "measured mode")
            with self.assertRaisesRegex(H.HarnessError, "exact frozen commit"):
                H.require_exact_frozen_head("b" * 40, "measured mode")
        finally:
            H.frozen_commit = old_frozen_commit

    def test_artifact_call_manifest_requires_exact_provider_path_set(self):
        old_rows = H.measured_manifest_rows
        with tempfile.TemporaryDirectory() as tmp:
            namespace = Path(tmp)
            try:
                H.write_json_atomic(namespace / "tasks" / "excluded.json", {"status": "excluded"})
                started = {"event": "started", "path": "interviews/one.json",
                           "started_at": "2026-08-24T00:00:00+00:00"}
                completed = {"event": "completed", "path": "interviews/one.json",
                             "sha256": "a" * 64}
                H.measured_manifest_rows = lambda current: [
                    {"run_id": "record-start-" + H.digest({"namespace": namespace.name, **started}, 20),
                     **started},
                    {"run_id": "record-complete-" + H.digest({"namespace": namespace.name, **completed}, 20),
                     **completed},
                ]
                H.verify_complete_call_manifest(namespace, {
                    "interviews/one.json", "tasks/excluded.json", "metadata.json", "record-manifest.jsonl"
                })
                H.measured_manifest_rows = lambda current: [
                    {"run_id": "record-start-" + H.digest({"namespace": namespace.name, **started}, 20),
                     **started}
                ]
                with self.assertRaisesRegex(H.HarnessError, "paths differ"):
                    H.verify_complete_call_manifest(namespace, {
                        "interviews/one.json", "metadata.json", "record-manifest.jsonl"
                    })
            finally:
                H.measured_manifest_rows = old_rows

    def test_measured_manifest_run_ids_bind_the_namespace(self):
        started = {"event": "started", "path": "interviews/one.json",
                   "started_at": "2026-08-24T00:00:00+00:00"}
        old_namespace = Path("m-old")
        new_namespace = Path("m-new")
        row = {
            "run_id": "record-start-" + H.digest(
                {"namespace": old_namespace.name, **started}, 20
            ),
            **started,
        }
        H.validate_measured_manifest_row(old_namespace, row)
        with self.assertRaisesRegex(H.HarnessError, "differs from its namespace"):
            H.validate_measured_manifest_row(new_namespace, row)

    def test_persisted_provider_identity_is_revalidated(self):
        profile = H.profile_map()["fable-subject"]
        record = {
            "status": "ok",
            "model": {
                "requested_model": profile["model"],
                "reported_models": [
                    profile["reported_identity_required"],
                    *profile["allowed_auxiliary_models"],
                ],
                "reported_providers": ["firstParty"],
            },
        }
        H.validate_model_metadata(record, profile, "interviews/example.json")
        record["model"]["requested_model"] = "substitute-model"
        with self.assertRaisesRegex(H.HarnessError, "requested model differs"):
            H.validate_model_metadata(record, profile, "interviews/example.json")
        judge = H.profile_map()["gpt-judge"]
        impossible = {
            "status": "ok",
            "model": {
                "requested_model": judge["model"],
                "reported_models": ["unreported-model"],
                "reported_providers": [],
                "identity_evidence": judge["identity_evidence"],
                "cli_version": "codex-cli test",
            },
        }
        with self.assertRaisesRegex(H.HarnessError, "reported model differs"):
            H.validate_model_metadata(impossible, judge, "judgments/example.json")
        record["model"] = {
            "requested_model": profile["model"],
            "reported_models": [profile["reported_identity_required"]],
            "reported_providers": [profile["reported_provider_required"], "unapproved"],
        }
        with self.assertRaisesRegex(H.HarnessError, "reported provider differs"):
            H.validate_model_metadata(record, profile, "interviews/example.json")
        deepseek = H.profile_map()["deepseek-reader"]
        deepseek_record = {
            "status": "pass",
            "model": {
                "provider": deepseek["provider"],
                "requested_model": deepseek["model"],
                "reported_models": [deepseek["reported_identity_required"]],
                "reported_providers": [],
            },
        }
        H.validate_model_metadata(deepseek_record, deepseek, "reader/example.json")
        del deepseek_record["model"]["provider"]
        with self.assertRaisesRegex(H.HarnessError, "configured provider metadata differs"):
            H.validate_model_metadata(deepseek_record, deepseek, "reader/example.json")

    def test_codex_minimum_version_is_required_before_exec(self):
        profile = H.profile_map()["gpt-judge"]
        old = mock.Mock(returncode=0, stdout="codex-cli 0.147.9\n", stderr="")
        with mock.patch.object(H.subprocess, "run", return_value=old):
            with self.assertRaisesRegex(H.HarnessError, "below required 0.148.0"):
                H.require_codex_cli_version(profile, "/bin/codex")
        current = mock.Mock(returncode=0, stdout="codex-cli 0.148.0\n", stderr="")
        with mock.patch.object(H.subprocess, "run", return_value=current):
            self.assertEqual(
                H.require_codex_cli_version(profile, "/bin/codex"), "codex-cli 0.148.0"
            )

    def test_finalize_requires_published_artifact_manifest_before_evidence(self):
        old_raw = H.RAW
        old_manifests = H.ARTIFACT_MANIFESTS
        old_gate = H.ensure_measured_gate
        old_verify = H.verify_measured_manifest
        old_namespace_check = H.validate_artifact_namespace
        old_id = H.measured_id
        with tempfile.TemporaryDirectory() as tmp:
            try:
                H.RAW = Path(tmp) / "raw"
                H.ARTIFACT_MANIFESTS = Path(tmp) / "manifests"
                H.ensure_measured_gate = lambda: "a" * 40
                H.verify_measured_manifest = lambda namespace: None
                H.validate_artifact_namespace = lambda namespace: None
                H.measured_id = lambda: "m-test"
                with self.assertRaisesRegex(H.HarnessError, "published raw-artifact manifest is absent"):
                    H.cmd_finalize(None)
            finally:
                H.RAW = old_raw
                H.ARTIFACT_MANIFESTS = old_manifests
                H.ensure_measured_gate = old_gate
                H.verify_measured_manifest = old_verify
                H.validate_artifact_namespace = old_namespace_check
                H.measured_id = old_id

    def test_pack_and_finalize_invoke_frozen_source_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {"batch_id": "m-test", "release": {"tag": "evidence-e09-m-test"}}
            manifest = {"archive": {"sha256": "a" * 64}}
            paths = (
                root / "staging" / "archive.tar.gz",
                root / "staging" / "manifest.json",
                root / "staging" / "plan.json",
                root / "artifacts" / "m-test.json",
            )
            with mock.patch.object(H, "ROOT", root), \
                 mock.patch.object(H, "RAW", root / "raw"), \
                 mock.patch.object(H, "ensure_measured_gate", return_value="a" * 40), \
                 mock.patch.object(H, "measured_id", return_value="m-test"), \
                 mock.patch.object(H, "artifact_plan", return_value=plan), \
                 mock.patch.object(H, "artifact_paths", return_value=paths), \
                 mock.patch.object(H.artifact_store, "pack", return_value=manifest), \
                 mock.patch.object(H.artifact_store, "require_local_frozen_source",
                                   side_effect=H.artifact_store.ArtifactError("frozen sentinel")) as frozen, \
                 mock.patch.object(H.artifact_store, "verify_source") as source:
                with self.assertRaisesRegex(H.HarnessError, "frozen sentinel"):
                    H.cmd_artifact_pack(mock.Mock(supersedes=None))
            frozen.assert_called_once_with(root, manifest)
            source.assert_not_called()

            manifest_dir = root / "manifests"
            H.write_json_atomic(manifest_dir / "m-test.json", {})
            with mock.patch.object(H, "ROOT", root), \
                 mock.patch.object(H, "RAW", root / "raw"), \
                 mock.patch.object(H, "ARTIFACT_MANIFESTS", manifest_dir), \
                 mock.patch.object(H, "ensure_measured_gate", return_value="a" * 40), \
                 mock.patch.object(H, "measured_id", return_value="m-test"), \
                 mock.patch.object(H, "validate_artifact_namespace"), \
                 mock.patch.object(H, "verify_measured_manifest"), \
                 mock.patch.object(H, "validate_artifact_binding", return_value=manifest), \
                 mock.patch.object(H, "artifact_plan", return_value=plan), \
                 mock.patch.object(H.artifact_store, "require_local_frozen_source",
                                   side_effect=H.artifact_store.ArtifactError("frozen sentinel")) as frozen, \
                 mock.patch.object(H, "verify_published_artifact") as remote:
                with self.assertRaisesRegex(H.HarnessError, "frozen sentinel"):
                    H.cmd_finalize(None)
            frozen.assert_called_once_with(root, manifest)
            remote.assert_not_called()

    def test_finalize_rebinds_source_after_remote_and_before_persisting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifests = root / "manifests"
            manifest_path = manifests / "m-test.json"
            H.write_json_atomic(manifest_path, {})
            plan = {"plan": True}
            manifest = {"manifest": True}
            with mock.patch.object(H, "ROOT", root), \
                 mock.patch.object(H, "RAW", root / "raw"), \
                 mock.patch.object(H, "ARTIFACT_MANIFESTS", manifests), \
                 mock.patch.object(H, "ensure_measured_gate", return_value="a" * 40), \
                 mock.patch.object(H, "measured_id", return_value="m-test"), \
                 mock.patch.object(H, "validate_artifact_namespace"), \
                 mock.patch.object(H, "verify_measured_manifest"), \
                 mock.patch.object(H, "validate_artifact_binding", return_value=manifest), \
                 mock.patch.object(H, "artifact_plan", return_value=plan), \
                 mock.patch.object(H, "verify_current_artifact_source",
                                   side_effect=[None, H.HarnessError("post-remote rebind")]) as source, \
                 mock.patch.object(H, "verify_published_artifact", return_value={"verified": True}) as remote:
                with self.assertRaisesRegex(H.HarnessError, "post-remote rebind"):
                    H.cmd_finalize(None)
            self.assertEqual(source.call_count, 2)
            remote.assert_called_once_with(manifest_path)

        with mock.patch.object(H, "verify_current_artifact_source",
                               side_effect=H.HarnessError("pre-persist rebind")) as source, \
             mock.patch.object(H, "write_or_verify_compact_result") as writer, \
             mock.patch.object(H, "ensure_ledger_lines") as ledger, \
             self.assertRaisesRegex(H.HarnessError, "pre-persist rebind"):
            H.persist_verified_compact_result(
                Path("raw"), Path("manifest"), plan, manifest,
                Path("results"), {"schema_version": 2, "lines": []}, None, [],
            )
        source.assert_called_once()
        writer.assert_not_called()
        ledger.assert_not_called()

    def test_finalize_manifest_must_bind_current_batch_freeze_and_commit(self):
        old_id = H.measured_id
        head = "a" * 40
        with tempfile.TemporaryDirectory() as tmp:
            namespace = Path(tmp) / "raw" / "m-test"
            manifest_path = Path(tmp) / "manifest.json"
            H.write_json_atomic(namespace / "metadata.json", {
                "experiment": "E-09",
                "base_commit": head,
                "freeze_sha256": H.sha256(H.E09 / "freeze.json"),
            })
            spec = H.load_json(H.DATA_FILES["artifact-spec.json"])
            frozen = H.load_json(H.E09 / "freeze.json")
            try:
                H.measured_id = lambda: "m-test"
                manifest = {
                    "schema_version": H.artifact_store.SCHEMA_VERSION,
                    "repository": spec["repository"],
                    "experiment": "E-09",
                    "batch_id": "m-test",
                    "frozen_commit": head,
                    "freeze_sha256": H.sha256(H.E09 / "freeze.json"),
                    "packager_commit": head,
                    "provenance": {
                        **frozen["files"],
                        "experiments/e09/freeze.json": H.sha256(H.E09 / "freeze.json"),
                    },
                    "provenance_index": "experiments/e09/freeze.json",
                    "sanitization_policy_source": "experiments/e09/artifact-spec.json",
                    "release": {
                        "tag": "evidence-e09-m-test",
                        "archive_asset_name": "m-test.raw.tar.gz",
                        "manifest_asset_name": "m-test.manifest.json",
                    },
                }
                H.write_json_atomic(manifest_path, manifest)
                self.assertEqual(H.validate_artifact_binding(namespace, manifest_path, head), manifest)
                manifest["batch_id"] = "m-other"
                H.write_json_atomic(manifest_path, manifest)
                with self.assertRaisesRegex(H.HarnessError, "current batch_id"):
                    H.validate_artifact_binding(namespace, manifest_path, head)
            finally:
                H.measured_id = old_id

    def test_unselected_or_rejected_rule_sources_invalidate_contract(self):
        payload = {
            "selected_evidence_ids": ["O01"],
            "selected_catalog_ids": ["U01"],
            "rejected_catalog_ids": ["U02"],
            "automatic_bans": [],
            "rules": [
                {"text": "Avoid stock framing.", "evidence_ids": [], "catalog_ids": ["U02"]},
                {"text": "Use reference codes.", "evidence_ids": ["O09"], "catalog_ids": []},
            ],
            "contract": "- Avoid stock framing.\n- Use reference codes.\n",
        }
        violations = H.contract_violations("treatment", payload)
        self.assertIn("rule_1_uses_unselected_catalog_id", violations)
        self.assertIn("rule_1_uses_rejected_catalog_id", violations)
        self.assertNotIn("selected_and_rejected_catalog_overlap", violations)
        self.assertIn("rule_2_uses_unselected_evidence", violations)
        self.assertIn("rule_2_uses_rejected_evidence", violations)

    def test_contract_must_exactly_match_ordered_rule_text(self):
        payload = {
            "selected_evidence_ids": ["O01"],
            "rules": [{"text": "Lead with the outcome.", "evidence_ids": ["O01"]}],
            "contract": "- Lead with the outcome.\n- Add an unsourced rule.\n",
        }
        self.assertIn("contract_does_not_exactly_match_rules", H.contract_violations("control", payload))
        payload["contract"] = "- Lead with the outcome.\n"
        self.assertNotIn("contract_does_not_exactly_match_rules", H.contract_violations("control", payload))

    def test_selected_and_rejected_catalog_ids_cannot_overlap(self):
        payload = {
            "selected_evidence_ids": [],
            "selected_catalog_ids": ["U01"],
            "rejected_catalog_ids": ["U01"],
            "automatic_bans": [],
            "rules": [],
            "contract": "",
        }
        self.assertIn("selected_and_rejected_catalog_overlap", H.contract_violations("treatment", payload))

    def test_task_judge_schema_pins_row_counts(self):
        schema = H.task_judge_schema("T01", 2, 1)
        valid = {"task_id": "T01", "required_pass": [True, True], "fatal_hits": [False]}
        self.assertEqual(H.validate_schema(valid, schema), [])
        valid["required_pass"] = [True]
        self.assertTrue(H.validate_schema(valid, schema))

    def test_human_adjudication_sheet_is_self_contained_and_blind(self):
        expected = {"blind-1": {
            "candidate_ids": ["c1"],
            "candidates": [{"candidate_id": "c1", "text": "candidate text"}],
            "response_context": "full response",
        }}
        rows = {"blind-1": [
            {"result": {"verdicts": [{"candidate_id": "c1", "pattern_id": "U01"}]}},
            {"result": {"verdicts": [{"candidate_id": "c1", "pattern_id": None}]}},
        ]}
        sheet = H.build_adjudication_pending(expected, rows, ["blind-1"])
        self.assertEqual(sheet["cases"][0]["response_context"], "full response")
        self.assertIn("taxonomy", sheet)
        rendered = H.canonical(sheet)
        for forbidden in ('"arm"', '"family"', '"rep"', '"condition"', '"path"'):
            self.assertNotIn(forbidden, rendered)

    def test_human_adjudication_has_one_resolution_per_current_disagreement(self):
        resolved = {"resolutions": [{"blind_id": "blind-1", "verdicts": []}]}
        self.assertEqual(H.adjudication_resolution_map(resolved, ["blind-1"]), {"blind-1": []})
        duplicate = {"resolutions": [resolved["resolutions"][0], resolved["resolutions"][0]]}
        with self.assertRaisesRegex(H.HarnessError, "one resolution per blind ID"):
            H.adjudication_resolution_map(duplicate, ["blind-1"])
        with self.assertRaisesRegex(H.HarnessError, "every and only pending blind ID"):
            H.adjudication_resolution_map(resolved, ["blind-2"])


if __name__ == "__main__":
    unittest.main()
