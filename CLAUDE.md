# meta-skills

Skills that review and improve other skills and agentic tools.

## Rules

- Plain english. Short sentences. One pass must be enough. No contradictions — fix the old rule, don't add a caveat.
- Weight-bearing choices go to the user as options with a recommendation. Durable decisions land in DECISIONS.md; run-scoped calls (fixture picks, batch naming, probe choice) stay in the run's own records — ledger lines, experiment notes.
- Imported ideas (papers, outside practices) are unproven until validated here. Each one lives in research/CLAIMS.md with a status and a test.
- An effectiveness claim in binding text cites our own evidence or carries [UNVERIFIED] plus "Falsifier:" naming the recorded thing that would prove it wrong.
- New skill or rule text lands only after a cold reader — a cheap model with no session context — restates its obligations correctly.
- Measure when we can. A score cited as evidence comes from a 5-run batch with variance (prior: C10, C11 — untested) and gets a second opinion from a different model family. Single runs are context, never evidence.
- Every skill run leaves one line in ledger/runs.jsonl (schema: ledger/README.md, D-012).
- An explicit user instruction controls whether a PR is draft or ready. Without one, keep it draft while work is incomplete, then mark it ready as soon as the planned implementation, validation, and pre-PR reviews are complete. Do not wait for a separate prompt or preserve a publishing tool's draft default.

## Map

- skills/<name>/SKILL.md — the skills. Frontmatter `status: draft | testing | proven`. Proven → symlink into ~/.claude/skills/<name>.
- fixtures/ — SKILL.md eval corpus: real files + planted-defect files with flaw manifests.
- research/sources/ — raw PDFs. Ingestion only.
- research/notes/ — one distilled note per paper. Read these, not the PDFs.
- research/CLAIMS.md — every borrowed idea: status, the test that moves it, the evidence.
- ledger/ — append-only run records: runs.jsonl, one JSON line per run.
- experiments/ — one dir per E-xx: frozen design, harness, raw outputs (D-023).
- docs/ — session prompts and design docs.
