# Kickoff — E-02: real-fixture reviews, user spot-check

Paste the prompt below into a fresh session in this repo, or just give this file's path.

---

Run experiment E-02 (docs/experiments.md): review-skill over the real fixture corpus, every finding spot-checked by the user. This is the second promotion gate for review-skill (the first was E-06: adj-20260721-161797bfb1, -69d5d03b9a).

Read first, in order: CLAUDE.md, DECISIONS.md, skills/review-skill/SKILL.md with references/rubric.md and scripts/, ledger/README.md, fixtures/README.md, docs/experiments.md (E-06 results and its queued-work list).

Ground rules:

- The reviewer is frozen at its committed sha for the whole experiment — no skill, rubric, or script edits once the first run starts. Anything found broken becomes queued work; never patch mid-eval. E-06's queued items stay queued unless E-02 shows they block precision.
- Real fixtures have no manifests, so there is no auto-match: every finding goes to the user. Cluster findings per fixture (same smell, overlapping spans, across repeats) and bring clusters through AskUserQuestion with a recommendation each; verdicts are fix-worthy | not-fix-worthy | wrong-evidence.

Scope — first fork, to the user with a recommendation: which snapshots. Current snapshot of each of the 7 skills (7 × 5 = 35 runs; version pairs are E-03's job) vs all 13 snapshots (65 runs) vs a 3-skill pilot first. Note skill-creator's current snapshot is the corpus's only LSB fail and is E-05's subject — reviewing it here is fine, distilling it is not.

Verdict recording — second fork, decide before any run drains: adjudicate.py only knows planted fixtures (spans TSVs), so user spot-check verdicts have no writer yet. Options: extend ledger/adjudicate.py with a spot-check mode that writes a type:adjudication line per batch from a verdicts worksheet (keeps the D-015/D-017 rule — deterministic script owns arithmetic and serialization; recommended), or a committed verdicts file under docs/. Consulting a second-family model headless on the design is encouraged (CLAUDE.md documents claude-kimi). Harness changes are not reviewer changes — they may land before runs start, gated the usual way, committed before the first batch.

The batches: E-06 protocol (docs/kickoff-e06.md). 5 fresh-subagent runs per snapshot, batch ids e02-<skill-name>, seq 1..5, finalize --outbox, one single --drain after all batches. Reviewer subagents get only the skill path, fixture path, batch args, and probe command (haiku headless, run from a directory outside any project). Second family: one snapshot of the chosen set re-run ×5 on kimi (batch e02-<name>-kimi; harness flags in docs/kickoff-e06.md) so the corpus has a cross-family anchor.

Analysis, after all verdicts:

- C01: precision per batch from user verdicts; the claim survives ~70%+.
- C02: median user-confirmed smells per file across the corpus (paper says ~10).
- C03: separate analysis pass, no reviewer involved — classify each reviewed snapshot's H2 sections against the 13-component taxonomy (research/notes/, the smell-study note); record the unclassifiable share.
- C08: category counts of confirmed findings — does instruction-quality lead?

Close out: move C01/C02/C03/C08 evidence in research/CLAIMS.md; mark E-02 done in docs/experiments.md with the ids at the start and results at the end; DECISIONS entries only where durable (D-016); new breakage becomes queued work. Final fork to the user: with E-06 and E-02 both in, does review-skill go testing → proven (symlink per D-002), or what blocks it?

Session rules: plain english. Weight-bearing forks go to the user as options with a recommendation. finalize.py and adjudicate.py are the only ledger writers. Commit before eval runs, never during them.
