# Kickoff — E-03: version-pair persistence

Paste the prompt below into a fresh session in this repo, or just give this file's path.

---

Run experiment E-03 (docs/experiments.md): version-pair persistence — do smells confirmed in an old snapshot persist into the current one unless deliberately fixed? Moves C07. Builds on E-02: the current snapshots' user-confirmed clusters are already in the ledger (the eight adj-20260723 spot-check lines).

Read first, in order: CLAUDE.md, DECISIONS.md (D-017 and D-020 are the adjudication design), skills/review-skill/SKILL.md with references/rubric.md, ledger/README.md, fixtures/README.md, docs/experiments.md (E-02 results and its queued-work list).

Ground rules:

- The reviewer is frozen at its committed sha for the whole experiment — no skill, rubric, or script edits once the first run starts. Anything found broken becomes queued work; never patch mid-eval. E-02's and E-06's queued items stay queued.
- Reviewer subagents are fresh and get only the skill path, fixture path, batch args, and probe command (haiku headless, run from a directory outside any project). They never read ledger/, docs/, research/, DECISIONS.md, or fixtures/planted/ — the E-02 lines on the current snapshots are answer-key-adjacent for this experiment.

The batches: E-02 protocol (docs/kickoff-e02.md). The six old snapshots — frontend-design 2025-12-04-0075614, grill-with-docs 2026-04-30-b843cb5, skill-creator 2026-02-06-1ed29a0, tdd 2026-04-28-62f43a1, test-driven-development 2025-10-17-48410c7, writing-skills 2026-01-14-a08f088 — × 5 fresh-subagent runs each, batch ids e03-<skill-name>, seq 1..5, finalize --outbox, one single --drain after all batches. karpathy-guidelines has no pair and sits out. Second family: one old snapshot re-run ×5 on kimi (harness flags in docs/kickoff-e06.md); writing-skills old would mirror the E-02 anchor — run-scoped pick, note it in the experiment notes.

Verdicts: spot-check mode (D-020) — spot-match, every cluster through AskUserQuestion with a recommendation each (fix-worthy | not-fix-worthy | wrong-evidence), spot-commit one line per batch.

The persistence analysis, after all verdicts — fork, to the user with a recommendation: how to match confirmed clusters across versions. Spans shift between versions, so matching is semantic (same smell + same file + same underlying defect). Options: the orchestrator proposes per-pair match tables and the user confirms each (mirrors the adjudication flow, keeps judgment with the user), or a script-assisted first pass on smell+file with the user adjudicating only the ambiguous remainder. Decide in the same fork where the persistence record lands: experiment notes in docs/experiments.md (per-pair numbers are analysis over committed adjudication lines and reproducible from them) or a new ledger line type (needs a writer amendment per D-017, gated and committed before runs start). Whichever lands, the persisted/fixed/new arithmetic is computed by script, never by hand.

C07 moves on the share of old confirmed smells still present in the current snapshots (the paper: smells rarely disappear once introduced). Watch the two sharply-reduced pairs — grill-with-docs and tdd were cut down upstream (D-007), so deletion-heavy evolution is exactly where persistence should break; distinguish "fixed" from "the section it lived in was deleted".

Close out: C07 evidence in research/CLAIMS.md; mark E-03 done in docs/experiments.md with the ids at the start and results at the end; DECISIONS entries only where durable (D-016); new breakage becomes queued work.

Session rules: plain english. Weight-bearing forks go to the user as options with a recommendation. finalize.py and adjudicate.py are the only ledger writers. Commit before eval runs, never during them.
