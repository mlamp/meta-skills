# Kickoff — E-06: fix the reviewer, revalidate deletion recall

Paste the prompt below into a fresh session in this repo, or just give this file's path.

---

Run experiment E-06: apply the queued E-01 fixes to review-skill, then prove the deletion fix on a new deletion-heavy planted fixture. E-01's baseline (ledger: adj-20260721-aeea8221b2, -0beccec7a6, -b58423aa64): recall 1.0 on insertion flaws, 0/4 on pure deletions, every run, both families where tested.

Read first, in order: CLAUDE.md, DECISIONS.md, skills/review-skill/SKILL.md with references/rubric.md and scripts/, ledger/README.md, fixtures/README.md, docs/experiments.md (E-01 results and the queued-work list).

Overfit guard, before anything else: never open fixtures/planted/*.manifest.md or *.spans.tsv from E-01 this session. The fix must generalize, not memorize the old answer keys — the queued-work list in docs/experiments.md is the only allowed description of the failures. The new fixture's flaws are invented fresh from its own base.

Part 1 — fixes. Commit them before any eval run, so run lines carry a clean reviewer sha.

1. Absence pass: add to the judgment step a per-dimension question — what does this skill's job imply should exist that is absent? (rules for foreseeable conflicts, plan-review gates, caveats for known failure modes, concrete specs where format matters). Write it generically. Consulting a second-family model headless on the design is encouraged (CLAUDE.md documents claude-kimi).
2. Standardize the cold-reader probe: a fixed question set in the skill or rubric, not improvised per run. E-01: cold-reader was the only dimension with score range 2 across identical runs.
3. Sharpen rubric cues: the ME vs MT boundary on absences (E-01: the same deleted spec was filed as ME by two runs and MT by three), and NTPD — decide whether an imperative in the description counts, and say so.
4. static_checks.py: report file line numbers, not frontmatter-stripped body lines.
5. ledger/adjudicate.py: harden worksheet parsing (a row with an empty verdict loses its trailing tab under naive stripping). Regression check: rerun `match` on the three e01 batches — the caught-sets must reproduce the committed adjudication lines exactly. This check may read the spans TSVs only through the script's output, not by opening them.
6. Gates: every changed piece of skill or rubric text passes a cold-reader probe (haiku headless: `claude --model haiku -p`, file piped in, no session context) per D-005 — fix or consciously dismiss every misread. Then one solo self-review of the updated skill through review-skill itself, committed to the ledger.
7. Bump review-skill frontmatter status draft → testing. Proven waits for E-06 results plus E-02.

Part 2 — the fixture. One new planted fixture from a vendored permissive base not yet planted (writing-skills or skill-creator per D-008; pick with a recommendation). Per D-013: ~12 flaws, at least one per judgment dimension, at least two static — and for E-06 at least half must be pure deletions of real guidance, with at least three leaving no vague residue behind. Manifest and spans TSV sibling to the fixture dir. Verify the static plants trip the checker. A fixture never changes after a recorded run references it.

Part 3 — the batch. E-01 protocol exactly (docs/kickoff-e01.md): 5 fresh-subagent runs on our family plus 5 on kimi — the second family has never been tested on deletions. Batch ids e06-<fixture> and e06-<fixture>-kimi, seq 1..5, finalize with --outbox, one single --drain, manifests closed until every run is drained. Reviewer subagents get only the skill path, fixture path, batch args, and probe command. Kimi harness details from E-01: `claude-kimi -p "<prompt>" --permission-mode acceptEdits --allowedTools "Bash" "Read" "Write" "Glob" "Grep" < /dev/null`, run in background; tell it to use Write, not Edit, for report fixes. Adjudicate with ledger/adjudicate.py; everything unmatched goes to the user through AskUserQuestion; commit adjudication lines.

Close out: compare deletion recall against the E-01 baseline; update C01, C06, C11 evidence in research/CLAIMS.md; DECISIONS entries only where durable (D-016); anything newly broken becomes queued work — never patch mid-eval. Add E-06 to docs/experiments.md at the start, mark it done with the adj ids at the end.

Session rules: plain english. Weight-bearing forks go to the user as options with a recommendation. finalize.py and adjudicate.py are the only ledger writers. Commit before eval runs, never during them.
