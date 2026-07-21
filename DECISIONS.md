# Decisions — append-only

One short entry per decision: the call, and why. Newest at the bottom. A decision is reversed by a new entry marking the old one superseded — never by editing history.

## D-001 · 2026-07-21 · Repo purpose and working style
Home of meta-skills: skills that review and improve other skills and agentic tools. All binding text is plain english and one-pass readable. Weight-bearing choices go to the user as options with a recommendation; the outcome lands here, when it's made — not at session end.

## D-002 · 2026-07-21 · Layout: skills/ + symlink promotion
Skills are authored in skills/<name>/SKILL.md with frontmatter status: draft | testing | proven. Proven skills become usable everywhere via a symlink in ~/.claude/skills. Rejected: plugin-marketplace scaffolding (overhead before a first skill exists) and project-local .claude/skills (unusable elsewhere). Why: the cheapest structure that works everywhere and is easy to restructure later.

## D-003 · 2026-07-21 · Research is unproven input, filed in three layers
Papers land as raw PDFs in research/sources/ (ingestion only), one distilled note per paper in research/notes/ (the read layer), and every borrowed idea in research/CLAIMS.md with status untested | testing | validated | refuted plus the test that would move it. Nothing from a paper is treated as true until validated here.

## D-004 · 2026-07-21 · Claim hygiene: own evidence or [UNVERIFIED] + falsifier
An effectiveness claim in binding text either cites our own evidence (a D-number, a ledger entry, a fixture result) or carries [UNVERIFIED] plus "Falsifier:" naming the recorded thing that would prove it wrong. A tag without a falsifier doesn't count.

## D-005 · 2026-07-21 · Cold-reader probe on binding text
New skill or rule text lands only after a model with no session context restates its obligations correctly. What it misreads gets fixed or consciously dismissed. First applied same day to this repo's CLAUDE.md (cold reader: Kimi K3, headless, file piped in, no session context): all four scenario answers correct, no misreads.

## D-006 · 2026-07-21 · Measurement: fixtures from day one, ledger designed with skill #1
Every skill run should leave a record; the ledger schema and location are decided during skill #1 design, when we know what a run produces. fixtures/ holds the eval corpus from day one: real SKILL.md files plus planted-defect files whose flaw manifests make recall computable. Scores use repeated runs and, when the score matters, a second model family. The repeated-runs rule is a prior, not a result — the claims behind it are C10/C11, untested.

## D-007 · 2026-07-21 · Real fixtures: vendored pinned snapshots with provenance, pairs where history moved
A real fixture is a skill's files copied unmodified at a pinned upstream commit, under fixtures/real/<name>/<commit-date>-<sha7>/, with PROVENANCE.md recording source, path, license, full SHAs, and re-fetch commands. Snapshots never change; a new upstream state gets a new snapshot dir. Where upstream history moved, take a pair (oldest useful + current) — the first probe for C07. First corpus: grill-with-docs and tdd (mattpocock/skills, MIT, version pairs — both slimmed sharply upstream; grill-with-docs is now a 7-line alias to sibling skills), and karpathy-guidelines (multica-ai/andrej-karpathy-skills, ~195k stars, no license — vendored while this repo is private, resolve before any public push; unchanged upstream since 2026-01-28). Why: fixtures must not move under recorded results, and provenance keeps every snapshot re-fetchable and auditable.
