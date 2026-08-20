#!/usr/bin/env python3
"""Tests for validate_artifacts.py."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_artifacts.py")


class ValidateArtifactsTests(unittest.TestCase):
    def run_validator(self, root, *args):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=root,
            capture_output=True,
            text=True,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"validator returned non-JSON output\nstdout={proc.stdout}\nstderr={proc.stderr}")
        return proc, payload

    def write(self, root, name, text):
        path = Path(root, name)
        path.write_text(text, encoding="utf-8")
        return path

    def write_bytes(self, root, name, value):
        path = Path(root, name)
        path.write_bytes(value)
        return path

    def test_valid_two_layer_multi_settings_style_and_derived_append(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Voice\n\n- Lead with the outcome.\n")
            delta = self.write(root, "delta.md", "# Project voice\n\n- Name issue IDs at the end.\n")
            style = self.write(
                root,
                "style.md",
                "---\ndescription: Project voice\nkeep-coding-instructions: true\n---\n"
                "# Voice\n\n- Keep the answer short.\n",
            )
            append = self.write(root, "append.md", "# Voice\n\n- Keep the answer short.\n")
            project_settings = self.write(
                root,
                "settings.json",
                '{"attribution":{"commit":"","pr":""}}\n',
            )
            local_settings = self.write(
                root,
                "settings.local.json",
                '{"outputStyle":"style"}\n',
            )
            proc, payload = self.run_validator(
                root,
                "--core",
                core,
                "--delta",
                delta,
                "--output-style",
                style,
                "--append",
                append,
                "--derived-from",
                style,
                "--settings",
                project_settings,
                "--settings",
                local_settings,
                "--expect-output-style",
                f"{local_settings}=style",
                "--expect-attribution-off",
                project_settings,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(len(payload["limitations"]), 3)

    def test_rules_reject_lf_crlf_and_bom_frontmatter(self):
        with tempfile.TemporaryDirectory() as root:
            files = (
                self.write(root, "lf.md", "---\ndescription: no\n---\nDo the thing.\n"),
                self.write_bytes(
                    root,
                    "crlf.md",
                    b"---\r\ndescription: no\r\n---\r\nDo the thing.\r\n",
                ),
                self.write_bytes(
                    root,
                    "bom.md",
                    b"\xef\xbb\xbf---\ndescription: no\n---\nDo the thing.\n",
                ),
            )
            for path in files:
                with self.subTest(path=path.name):
                    proc, payload = self.run_validator(root, "--rules", path)
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn(payload["status"], ("fail",))

    def test_append_rejects_frontmatter(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.write(root, "source.md", "Do the thing.\n")
            append = self.write(
                root,
                "append.md",
                "---\ndescription: forbidden\n---\nDo the thing.\n",
            )
            proc, payload = self.run_validator(
                root,
                "--append",
                append,
                "--derived-from",
                source,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("must not contain frontmatter", payload["error"])

    def test_output_style_requires_boolean_true(self):
        with tempfile.TemporaryDirectory() as root:
            style = self.write(
                root,
                "style.md",
                '---\ndescription: Voice\nkeep-coding-instructions: "true"\n---\nDo the thing.\n',
            )
            proc, payload = self.run_validator(root, "--output-style", style)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("boolean keep-coding-instructions", payload["error"])

    def test_output_style_rejects_missing_description_unknown_key_and_empty_body(self):
        cases = {
            "missing.md": "---\nkeep-coding-instructions: true\n---\nDo it.\n",
            "unknown.md": "---\ndescription: Voice\nunknown: value\nkeep-coding-instructions: true\n---\nDo it.\n",
            "empty.md": "---\ndescription: Voice\nkeep-coding-instructions: true\n---\n# Voice\n",
        }
        with tempfile.TemporaryDirectory() as root:
            for name, text in cases.items():
                with self.subTest(name=name):
                    style = self.write(root, name, text)
                    proc, payload = self.run_validator(root, "--output-style", style)
                    self.assertEqual(proc.returncode, 1)
                    self.assertEqual(payload["status"], "fail")

    def test_empty_delta_fails_but_fenced_example_counts_as_content(self):
        with tempfile.TemporaryDirectory() as root:
            empty = self.write(root, "empty.md", "# Project voice\n")
            example = self.write(
                root,
                "example.md",
                "# Example\n\n```text\nA project-specific response.\n```\n",
            )
            empty_proc, empty_payload = self.run_validator(root, "--delta", empty)
            example_proc, _ = self.run_validator(root, "--delta", example)
            self.assertEqual(empty_proc.returncode, 1)
            self.assertIn("has no content", empty_payload["error"])
            self.assertEqual(example_proc.returncode, 0)

    def test_slot_detection_rejects_documented_slots_without_blocking_markdown(self):
        with tempfile.TemporaryDirectory() as root:
            good = self.write(
                root,
                "good.md",
                "# Voice\n\n"
                "- Install at ~/.claude/rules/<name>.md.\n"
                "- Press <Ctrl+C>, visit <https://example.com>, or use <details>.\n"
                "- Inline code such as `<Component value={{runtime.value}} />` is literal.\n",
            )
            bad_values = (
                "{{PROJECT}}",
                "{{ PROJECT NAME }}",
            )
            good_proc, _ = self.run_validator(root, "--rules", good)
            self.assertEqual(good_proc.returncode, 0)
            for index, value in enumerate(bad_values):
                with self.subTest(value=value):
                    bad = self.write(root, f"bad-{index}.md", f"# Voice\n\n{value}\n")
                    bad_proc, payload = self.run_validator(root, "--rules", bad)
                    self.assertEqual(bad_proc.returncode, 1)
                    self.assertIn("unfilled template slot", payload["error"])

    def test_output_style_rejects_slot_in_frontmatter(self):
        with tempfile.TemporaryDirectory() as root:
            style = self.write(
                root,
                "style.md",
                "---\ndescription: {{ DESCRIPTION }}\nkeep-coding-instructions: true\n---\nDo it.\n",
            )
            proc, payload = self.run_validator(root, "--output-style", style)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("unfilled template slot", payload["error"])

    def test_slot_detection_ignores_fenced_project_examples(self):
        with tempfile.TemporaryDirectory() as root:
            delta = self.write(
                root,
                "delta.md",
                "# Project examples\n\n```tsx\n<Component value={{project.value}} />\n```\n",
            )
            proc, payload = self.run_validator(root, "--delta", delta)
            self.assertEqual(proc.returncode, 0, payload)
            self.assertEqual(payload["status"], "pass")

    def test_fence_scanner_matches_marker_and_length(self):
        cases = (
            "~~~text\n```tsx\n<Component value={{project.value}} />\n```\n~~~\n",
            "````text\n```tsx\n<Component value={{project.value}} />\n```\n````\n",
            "```text\n~~~tsx\n<Component value={{project.value}} />\n~~~\n```\n",
        )
        with tempfile.TemporaryDirectory() as root:
            for index, example in enumerate(cases):
                with self.subTest(index=index):
                    core = self.write(root, f"core-{index}.md", "# Core\n\n- Keep it short.\n")
                    delta = self.write(
                        root,
                        f"delta-{index}.md",
                        f"# Examples\n\n{example}\n- Name issue IDs at the end.\n",
                    )
                    proc, payload = self.run_validator(
                        root, "--core", core, "--delta", delta
                    )
                    self.assertEqual(proc.returncode, 0, payload)

    def test_duplicate_after_nested_fence_still_fails(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Core\n\n- Keep it short.\n")
            delta = self.write(
                root,
                "delta.md",
                "# Example\n\n````text\n```tsx\n- Keep it short.\n```\n````\n\n"
                "- Keep it short.\n",
            )
            proc, payload = self.run_validator(
                root, "--core", core, "--delta", delta
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("exact duplicate instruction lines", payload["error"])

    def test_unclosed_fenced_block_fails(self):
        with tempfile.TemporaryDirectory() as root:
            delta = self.write(root, "delta.md", "# Example\n\n```text\nunclosed\n")
            proc, payload = self.run_validator(root, "--delta", delta)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("unclosed fenced block", payload["error"])

    def test_settings_types_and_strict_json(self):
        with tempfile.TemporaryDirectory() as root:
            cases = {
                "type.json": '{"outputStyle":7,"attribution":"off"}\n',
                "duplicate.json": '{"outputStyle":"one","outputStyle":"two"}\n',
                "constant.json": '{"value":NaN}\n',
                "root.json": '[]\n',
            }
            for name, text in cases.items():
                with self.subTest(name=name):
                    settings = self.write(root, name, text)
                    proc, payload = self.run_validator(root, "--settings", settings)
                    self.assertEqual(proc.returncode, 1)
                    self.assertEqual(payload["status"], "fail")

    def test_settings_expectations_target_one_file_and_fail_on_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            project = self.write(root, "settings.json", '{}\n')
            local = self.write(root, "settings.local.json", '{"outputStyle":"actual"}\n')
            proc, payload = self.run_validator(
                root,
                "--settings",
                project,
                "--settings",
                local,
                "--expect-output-style",
                f"{local}=expected",
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("must equal 'expected'", payload["error"])

    def test_attribution_expectation_fails_on_wrong_value(self):
        with tempfile.TemporaryDirectory() as root:
            settings = self.write(
                root,
                "settings.json",
                '{"attribution":{"commit":"coauthor","pr":""}}\n',
            )
            proc, payload = self.run_validator(
                root,
                "--settings",
                settings,
                "--expect-attribution-off",
                settings,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("attribution must equal", payload["error"])

    def test_exact_duplicates_fail_across_core_delta_and_existing(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Voice\n\n- Lead with the outcome.\n")
            delta = self.write(root, "delta.md", "# Project\n\n- Name issue IDs at the end.\n")
            existing = self.write(
                root,
                "CLAUDE.md",
                "---\npaths: src/**\n---\nLead with the outcome.\n",
            )
            proc, payload = self.run_validator(
                root,
                "--core",
                core,
                "--delta",
                delta,
                "--existing",
                existing,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("exact duplicate instruction lines", payload["error"])

    def test_existing_frontmatter_and_fenced_examples_do_not_false_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Voice\n\n- Lead with the outcome.\n")
            first = self.write(
                root,
                "first.md",
                "---\ndescription: Shared\n---\n```text\nSame example.\n```\nFirst unique rule.\n",
            )
            second = self.write(
                root,
                "second.md",
                "---\ndescription: Shared\n---\n```text\nSame example.\n```\nSecond unique rule.\n",
            )
            proc, payload = self.run_validator(
                root,
                "--core",
                core,
                "--existing",
                first,
                "--existing",
                second,
            )
            self.assertEqual(proc.returncode, 0, payload)

    def test_duplicate_detection_includes_output_style_body(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Voice\n\n- Lead with the outcome.\n")
            style = self.write(
                root,
                "style.md",
                "---\ndescription: Voice\nkeep-coding-instructions: true\n---\n"
                "Lead with the outcome.\n",
            )
            proc, payload = self.run_validator(
                root,
                "--core",
                core,
                "--output-style",
                style,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("exact duplicate instruction lines", payload["error"])

    def test_derived_append_must_match_valid_stripped_source_exactly(self):
        with tempfile.TemporaryDirectory() as root:
            style = self.write(
                root,
                "style.md",
                "---\ndescription: Voice\nkeep-coding-instructions: true\n---\nDo the thing.\n",
            )
            drifted = self.write(root, "drifted.md", "Do the thing.")
            proc, payload = self.run_validator(
                root,
                "--append",
                drifted,
                "--derived-from",
                style,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("differs from canonical sources", payload["error"])

    def test_derived_append_concatenates_sources_in_order(self):
        with tempfile.TemporaryDirectory() as root:
            core = self.write(root, "core.md", "# Core\n\nDo the first thing.\n")
            delta = self.write(root, "delta.md", "# Delta\n\nDo the second thing.\n")
            append = self.write(
                root,
                "append.md",
                "# Core\n\nDo the first thing.\n\n# Delta\n\nDo the second thing.\n",
            )
            proc, payload = self.run_validator(
                root,
                "--append",
                append,
                "--derived-from",
                core,
                "--derived-from",
                delta,
            )
            self.assertEqual(proc.returncode, 0, payload)

    def test_derived_append_trims_whitespace_only_edge_lines(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.write(
                root,
                "source.md",
                "  \n\n# Core\n\nDo the first thing.\n \t\n",
            )
            append = self.write(root, "append.md", "# Core\n\nDo the first thing.\n")
            proc, payload = self.run_validator(
                root,
                "--append",
                append,
                "--derived-from",
                source,
            )
            self.assertEqual(proc.returncode, 0, payload)

    def test_derived_source_must_be_valid(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.write(root, "source.md", "Do {{ THING }}.\n")
            append = self.write(root, "append.md", "Do {{ THING }}.\n")
            proc, payload = self.run_validator(
                root,
                "--append",
                append,
                "--derived-from",
                source,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("unfilled template slot", payload["error"])

    def test_argument_errors_are_json(self):
        with tempfile.TemporaryDirectory() as root:
            proc, payload = self.run_validator(root)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(payload["status"], "fail")
            self.assertIn("provide at least one artifact", payload["error"])

    def test_missing_file_is_json_failure(self):
        with tempfile.TemporaryDirectory() as root:
            proc, payload = self.run_validator(root, "--rules", "missing.md")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(payload["status"], "fail")
            self.assertIn("cannot read UTF-8 text", payload["error"])


if __name__ == "__main__":
    unittest.main()
