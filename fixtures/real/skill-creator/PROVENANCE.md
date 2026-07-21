# provenance — skill-creator

- Source: https://github.com/anthropics/skills · path `skills/skill-creator` · Apache-2.0 (LICENSE.txt inside each snapshot)
- Why taken: official META skill — a skill for making skills, prime dogfood target for the reviewer. Evolved opposite to the mattpocock fixtures: it grew, 7 files / 18k SKILL.md → 18 files / 33k SKILL.md (C05 length-threshold material).
- Path history: 5 commits, 2025-12-01 → 2026-04-20. Retrieved 2026-07-21.

Snapshots — dir is `<commit-date>-<sha7>`; content is the path at that commit, unmodified:

- 2026-02-06-1ed29a0 · 1ed29a03dc852d30fa6ef2ca53a67dc2c2c2c563 · "Update skill-creator and make scripts executable"
  Files (7): SKILL.md (18k), references/output-patterns.md, references/workflows.md, scripts/init_skill.py, scripts/package_skill.py, scripts/quick_validate.py, LICENSE.txt.
- 2026-04-20-b9e19e6 · b9e19e6f44773509fbdd7001d77ff41a49a486c1 · "Fill in Apache 2.0 copyright notice…" (last touch; content changes landed 2026-03-06)
  Files (18): SKILL.md (33k), agents/{analyzer,comparator,grader}.md, assets/eval_review.html, eval-viewer/{generate_review.py,viewer.html}, references/schemas.md, scripts/ (8 files incl. run_eval.py, run_loop.py, improve_description.py), LICENSE.txt.

Re-fetch any file: `curl -fsSL https://raw.githubusercontent.com/anthropics/skills/<full-sha>/<path>`
