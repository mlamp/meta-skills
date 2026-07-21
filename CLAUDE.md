# meta-skills

Skills that review and improve other skills and agentic tools.

## Rules

- Plain english. Short sentences. One pass must be enough. No contradictions — fix the old rule, don't add a caveat.
- Weight-bearing choices go to the user as options with a recommendation. Every decision lands in DECISIONS.md.
- Imported ideas (papers, outside practices) are unproven until validated here. Each one lives in research/CLAIMS.md with a status and a test.
- An effectiveness claim in binding text cites our own evidence or carries [UNVERIFIED] plus "Falsifier:" naming the recorded thing that would prove it wrong.
- New skill or rule text lands only after a cold reader — a cheap model with no session context — restates its obligations correctly.
- Measure when we can. Repeated runs, not single runs (prior: C10, C11 — untested). A score that matters gets a second opinion from a different model family.
- Every skill run should leave a record. Ledger schema: decided with skill #1 (D-006).

## Map

- skills/<name>/SKILL.md — the skills. Frontmatter `status: draft | testing | proven`. Proven → symlink into ~/.claude/skills/<name>.
- fixtures/ — SKILL.md eval corpus: real files + planted-defect files with flaw manifests.
- research/sources/ — raw PDFs. Ingestion only.
- research/notes/ — one distilled note per paper. Read these, not the PDFs.
- research/CLAIMS.md — every borrowed idea: status, the test that moves it, the evidence.
- docs/ — session prompts and design docs.
