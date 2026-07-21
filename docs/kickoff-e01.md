# Kickoff — E-01: first eval batch for review-skill

Paste the prompt below into a fresh session in this repo, or just give this file's path.

---

Run experiment E-01 (docs/experiments.md): the first planted-fixture eval batch for review-skill.

Read first, in order: CLAUDE.md, DECISIONS.md (D-009–D-015 are the skill and ledger design), skills/review-skill/SKILL.md and references/rubric.md, ledger/README.md, fixtures/README.md (eval protocol), docs/experiments.md.

Contamination rules, before anything else:

- Never open fixtures/planted/*.manifest.md until every review run has drained into the ledger. Manifests are answer keys (D-013).
- Reviewer runs are fresh subagents. Each gets only the reviewer skill and the fixture path — no session context, no other runs' findings, no manifest content, no expected flaw counts.

The batch:

1. Two fixtures (fixtures/planted/tdd-p1, fixtures/planted/frontend-design-p1) × 5 repeats = 10 runs on our model family. Each run follows skills/review-skill/SKILL.md exactly, finalizing with --outbox and --batch-id e01-<fixture>, --batch-seq 1..5. Cold-reader probe per run via a cheap headless model; mark estimated when unavailable.
2. Second family, per the protocol in fixtures/README.md: one batch of 5 on one fixture with a different model family as the reviewer, same outbox protocol.
3. Drain all outboxes into ledger/runs.jsonl — finalize.py --drain, one drainer, nothing else touches the ledger.
4. Only now open the manifests. Auto-match findings to planted flaws (smell_id + file + line overlap). Everything unmatched goes to the user through AskUserQuestion: planted-but-missed stays missed; found-but-unplanted is adjudicated pre-existing-real or false positive.
5. Compute per fixture and per family: recall on planted flaws, precision after adjudication, run-to-run agreement and flip rates across the 5 repeats, score variance. Record results as type: adjudication ledger lines referencing the run_ids.
6. Close out: CLAIMS.md status moves with our own evidence (C01 precision, C06 vs the paper's F1 0.78, C11 flip rate, C02 from confirmed pre-existing counts). DECISIONS entries for every call made. Anything E-01 reveals as broken in the skill, rubric, or finalizer becomes queued work — record it; never patch mid-eval.

Session rules: plain english. Weight-bearing forks go through AskUserQuestion with options and a recommendation. Decisions land in DECISIONS.md the moment they're made. Fixtures and recorded runs never change (D-007, D-013) — a mid-eval bug means a new batch, not edited history.
