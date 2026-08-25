# meta-skills

Skills that review and improve other skills and agentic tools — with every effectiveness claim measured here before it's believed. Borrowed ideas enter a claims register as untested; experiments move them; the ledger keeps every run.

## The skills

- **[agent-voice](skills/agent-voice/SKILL.md)** (draft) — generates a two-layer communication contract that makes a verbose frontier model direct: a user-level core (your voice, all projects) plus a per-project delta. Routes to settings what settings control, migrates voice rules out of your existing CLAUDE.md instead of duplicating them. Theory: [docs/communication-contracts.md](docs/communication-contracts.md).
- **[review-skill](skills/review-skill/SKILL.md)** (proven) — reviews a SKILL.md against a 26-smell rubric with scripted static checks and a cold-reader probe. Precision never below 0.94 across 65 adjudicated runs on planted and real corpora.

## What's measured (the short version)

- A communication contract cuts model output tokens **36–68%** at equal task success and drives tic phrases and em-dash chains to zero — in two model families, single-turn (E-07, 60 runs) and ~37k tokens deep into a session (E-08, 25 sessions).
- **Where you put it doesn't matter**: system-prompt placement vs CLAUDE.md placement was indistinguishable in both experiments. The community belief that the system prompt is the high-leverage location was refuted for every regime we could test (claim C17).
- Skill smells persist: 64% of confirmed defects survived 2.5–8 months of upstream evolution unless the section containing them was deleted outright (E-03).

Every number traces to a JSON line in [ledger/runs.jsonl](ledger/README.md) with pinned file hashes, and every claim's status lives in [research/CLAIMS.md](research/CLAIMS.md). Experiment designs are frozen and committed before their runs ([docs/experiments.md](docs/experiments.md)).

## Use agent-voice on your project

Three ways, by increasing involvement:

**Fast path — just take the core.** Copy the user-core block from [skills/agent-voice/references/contract-template.md](skills/agent-voice/references/contract-template.md) into `~/.claude/rules/voice.md` and edit the banned-phrase list. Add a project delta only for examples, terms, or rules that are wrong elsewhere.

**Full flow — let your harness run the skill.** Paste this into Claude Code (or any harness that can fetch a URL):

```
Fetch https://raw.githubusercontent.com/mlamp/meta-skills/main/skills/agent-voice/SKILL.md
and https://raw.githubusercontent.com/mlamp/meta-skills/main/skills/agent-voice/references/contract-template.md
and follow the skill for my current project: inventory my instruction stack, interview me,
then generate the two-layer contract. Skip the skill's ledger step — that record belongs
to its home repo, not mine.
```

**Casual — cherry-pick.** Ask your harness: *"Review the two files above and propose which parts are worth adopting for this project."* Lowest commitment; you get a proposal instead of files.

## Map

- `skills/<name>/SKILL.md` — the skills; frontmatter `status: draft | testing | proven`.
- `research/CLAIMS.md` — every borrowed idea: status, the test that moves it, the evidence.
- `ledger/` — append-only run records, one JSON line per run, written only by scripts.
- `experiments/` — one dir per experiment: frozen design and harness in Git; measured raw bundles in immutable releases; manifests and results in Git.
- `fixtures/` — SKILL.md eval corpus: pinned real snapshots + planted-defect files with answer keys.
- `docs/` — theory and design docs, experiment queue, session kickoffs.
- `DECISIONS.md` — durable decisions, append-only.

## House rules

Plain English, one pass must be enough. A recorded score means 5 repeated runs with variance plus a second model family. New binding text lands only after a cold reader — a cheap model with no context — restates its obligations correctly. Scripts own every record; models never hand-write JSON, dates, or ids.

## License

MIT for this repo's own content. Vendored fixtures keep their upstream licenses (see each `fixtures/real/<name>/PROVENANCE.md`); one unlicensed upstream snapshot was removed before publication and is re-fetchable locally via its PROVENANCE.
