# Claims register

Borrowed ideas are unproven here until our own evidence moves them. Status: untested | testing | validated | refuted. Every claim names the test that would move it. Evidence means our own records — ledger entries, fixture results, D-numbers — never "the paper says so".

Notes in research/notes/, PDFs in research/sources/. The harness that runs the tests: review-skill (D-009–D-013), planted fixtures under fixtures/planted/, records in ledger/runs.jsonl, queue in docs/experiments.md.

## From arXiv:2607.01456 (skill smells study)

- C01 [validated] The 26-smell catalog works as a review rubric for SKILL.md files — most hits are worth fixing.
  Test: run the smell checks on real fixtures; user spot-checks findings; survives if precision stays useful (~70%+). Evidence: E-01 (adj-20260721-aeea8221b2, -0beccec7a6, -b58423aa64): precision after user adjudication 1.0 / 0.969 / 1.0 per batch — 2 false positives across 15 runs. E-06 (adj-20260721-161797bfb1, -69d5d03b9a): precision 1.0 in all 10 runs of both families, including every absence-pass finding. E-02 (adj-20260723-, eight lines: 0837aedeaf, 955ae5b2b6, 06cfed1144, c0e3044fff, 88a5e09ce2, 6173065b52, 45dcdb14c9, 4215f2c292): 40 runs over all 7 current real snapshots + a kimi anchor, 243 findings, 96 user-adjudicated clusters — strict precision (fix-worthy only) pooled 0.947–1.0 per batch, grounded precision 1.0 everywhere, zero wrong-evidence verdicts. All 4 not-fix-worthy clusters were 1-of-5-run singletons; every cluster found by 2+ runs was fix-worthy. 65 runs cumulative across planted and real corpora, both families, precision never below 0.94.
- C02 [validated] Smells are pervasive: real skills average ~10 smells, so near-zero hits means a broken detector, not a clean corpus.
  Test: median hits per file across 10+ real fixtures. Evidence: E-01 confirmed pre-existing smells in unmodified base text (4 in frontend-design, 1 in tdd's mocking.md). E-02 (the eight adj-20260723 lines): user-confirmed fix-worthy clusters per skill across the 7 current snapshots: 4, 7, 8, 8, 12, 19, 19 — median 8, mean 11, against the paper's average 10.5. E-03 met the pre-registered 10+ condition: with the 6 old snapshots (13, 12, 13, 8, 13, 25 fix-worthy clusters), 13 fable batches over 7 distinct skills, median 12, mean 13.2. Caveat: snapshots of the same skill are not independent samples; 7 distinct skills underlie the 13 batches.
- C03 [testing] The 13-component taxonomy covers what real SKILL.md bodies contain; usable as the structural vocabulary of review output.
  Test: classify fixtures' H2 sections against it; unclassifiable share stays low. Evidence: E-02 close-out pass (no reviewer involved): 58 real H2 sections across the 7 current snapshots (code-fenced template headings excluded; grill-with-docs has none), classified by hand against the 13 components. 57/58 mapped — Task (incl. the platform-variant sections under environment variation), Introduction, Principles, Practice, Evaluation, References, Context, Usecase, Output Format all used; only writing-skills' closing "The Bottom Line" needed Other. Unclassifiable share ~2% (~3% counting the rationale-prose "Why Order Matters" as Other). One session's hand pass; a second classifier should replicate before validated.
- C04 [untested] Descriptions shaped [what it does] + [when to use] + [keywords] trigger better than free-form ones.
  Test: A/B one skill with both description forms on trigger-worthy and distractor tasks, repeated runs; compare invocation precision/recall. Evidence: —
- C05 [untested] Bodies over ~5,000 words hurt outcomes (context bloat).
  Test: A/B a long skill vs its distilled variant on the same tasks. Evidence: —
- C06 [testing] An LLM judge can detect the semantic smells around F1 0.78 — good enough to pre-screen, not to auto-fail.
  Test: label a fixture subset ourselves; compute precision/recall for our judge, per model family. Evidence: E-01, pooled over the 18 planted semantic flaws: claude-fable-5 recall 0.778, precision 0.979, F1 ≈ 0.87 — every miss is a pure-deletion flaw; kimi-k3 on tdd-p1 F1 ≈ 0.98. E-06, deletion-heavy corpus (skill-creator-p1, 10 semantic plants, adj-20260721-161797bfb1/-69d5d03b9a): fable per-flaw recall 0.70, precision 1.0, F1 ≈ 0.82 — still above 0.78 with the absence pass; kimi 0.54 / 1.0, F1 ≈ 0.70 — first below-paper number, concentrated on absences outside SKILL.md and judgment plants. Deletion recall specifically: fable 0/4 in E-01 → union 6/8 in E-06; kimi untested → 4/8.
- C07 [testing] Smells persist once introduced unless deliberately fixed.
  Test: version-pair fixtures in fixtures/real/ (review old vs current snapshots); later, our own skills' git history. Evidence: E-03 (adj-20260812 lines + experiments/e03/persistence.py): 43/67 confirmed (smell, file) keys persisted across 2.5–8-month gaps (fable 35/58, kimi anchor 8/9); at least 13 of the 24 resolutions were deletion- or rewrite-driven, not targeted fixes, so persistence absent deliberate rework is high — test-driven-development kept all 7 with identical spans. One matching rule (smell+file, hand-checked remainder, two label-only matches reclassified); stays testing until a second matcher or our own git history replicates.

## Communication contracts (theory: docs/communication-contracts.md; notes: disler-fixing-smartass-opus-5, collected-writing-for-humans)

- C13 [testing] A banned-phrase / negative-pattern list in the system prompt suppresses the listed tics.
  Test: E-07 — fixed task suite, baseline first, 5 runs per arm (stock vs contract), regex hits on phrases that appear in baseline, final responses only; second family. Evidence: E-07 (r-20260817-4cccea322c opus, r-20260817-8fbcc01b2b kimi): banned hits 7→0 (opus) and 2→0 (kimi) in both contract arms; em-dash mean 6.5→1.2 (sysprompt) →0.07 (claudemd) opus, 4.8→0.6→0 kimi; output tokens −36% to −52% (sysprompt arm) at 60/60 judge pass. E-08 (r-20260817-d4d49120dc, -48eac1a620): the effect holds at depth — probe at ~37k context tokens, opus 959→502/544 tokens (−48%), em-dash 5.6→0.8/0.2, judge 25/25, both placements, both families. One task family; stays testing until a broader suite or real-session data.
- C14 [untested] Reference-point codes (D1, R3, …) cut follow-up cost without losing referability.
  Test: scripted multi-turn follow-ups ("expand R2"), 5 runs per arm; token counts and correct code resolution. Evidence: —
- C15 [untested] Inline aliases (`scr`, `foc`) expand reliably when sent alone and never inside longer text.
  Test: repeated runs of alias-alone and alias-in-sentence prompts; expansion and false-trigger rates. Evidence: —
- C16 [untested] Do/don't example pairs move style compliance more than rule text alone.
  Test: A/B rules-only vs rules-plus-examples on the same suite; tic hits plus a blinded style judgment. Evidence: —
- C17 [refuted] The same contract text gets better compliance from the system prompt (output style) than from CLAUDE.md.
  Test: identical text in each location, 5 runs per arm per family; tic hits and output tokens. Evidence: E-07 (single-turn): direction contradicted — the CLAUDE.md arm matched or beat the sysprompt arm in both families (opus tokens 670/294/635 vs 716/581/789 per task; kimi 224 vs 292). E-08 (r-20260817-d4d49120dc, -48eac1a620): probe at ~37k context tokens after 4 filler turns — placements indistinguishable (opus 502 vs 544 output tokens, stdev 162/94, em-dash 0.8 vs 0.2; kimi 172 vs 174), contract fully effective at depth in both, judge 25/25. Never supported across two experiments; refuted for single-turn and ~37k-token sessions. Reopen only if 100k+ contexts or post-compaction behavior show a gap.
- C18 [untested] Explicit drive rules (a framed multi-step task is one slice; the user is the interrupter) reduce mid-task checkpoint questions.
  Test: scripted multi-step tasks, 5 runs per arm; count checkpoint/offramp questions and unprompted completion. Evidence: —

## From Cursor pstack `unslop` (note: cursor-pstack-unslop)

- C19 [untested] Adding six recognition prompts to a fixed inventory in a one-round interview identifies at least one additional manifest-listed, user-relevant voice pattern on average in both model families.
  Test: E-09 — inventory-only versus the same inventory plus U01–U06, five trials per arm and family. Fable and Kimi are separate interviewer/generator families. A simulated interviewee sees only a frozen manifest extracted by a no-context process from pre-2026-08-21 voice artifacts and corrections; input hashes are recorded. Both arms use the same frozen base tree. Remove this source note, D-029, and C19–C22 from both views before any trial. Give only the U01–U06 table and its boundary column to treatment as an interview attachment. Record the base commit, shared view diff, attachment hash, and complete instruction stack. Record the unaided-recall list, selected-pattern count and coverage, every run, mean, and variance. Evidence: —
  Falsifier: in either family, the catalog-assisted mean gain over inventory-only is less than one manifest-listed pattern.
- C20 [untested] The six prompts preserve or improve relevant coverage per contract token, keep the catalog-arm median at no more than one irrelevant selection per interview, and add no more than one mean task failure per trial.
  Test: E-09 — record normalized contract tokens after fixed boilerplate, manifest-listed selections per 100 contract tokens, irrelevant selections, and fixed-suite task failures for every trial, with mean and variance by arm and family. Deterministic matchers own counts; one fixed, blinded third-family judge owns task success. Evidence: —
  Falsifier: in either family, catalog-arm manifest-listed selections per 100 contract tokens are lower than inventory-only, catalog-arm median irrelevant selections exceed one per interview, or catalog-arm mean task failures per trial exceed inventory-only by more than one task.
- C21 [untested] For the same user-selected tic set, adding suppression rules increases semantically adjacent substitute tics.
  Test: E-09 nested comparison — suppression versus no suppression with the same selected tic set, generator, and tasks; five paired trials per condition and model family. Freeze the listed-tic matcher, substitute map, rubric, and worked examples before reading outputs. A blinded judge records substitute-tic counts; report raw counts, counts per listed tic suppressed, mean, and variance. Evidence: —
  Falsifier: in either family, the suppression condition's mean adjacent substitute-tic count is no higher than its matched no-suppression condition.
- C22 [untested] Contracts from catalog-assisted interviews reduce the manifest-wide listed-tic rate in task outputs more than contracts from inventory-only interviews.
  Test: E-09 — run the fixed task set with each generated contract, five trials per arm and family. Apply the same frozen manifest-wide matcher to every output and report hits per 1,000 output tokens. Record every output, rate, mean, variance, and task success. Evidence: —
  Falsifier: in either family, the catalog-assisted arm's mean manifest-wide listed-tic rate is no lower than inventory-only.

## From arXiv:2509.20497 (prompt debt study)

- C08 [testing] Instruction-style text is the biggest debt magnet; clarity and length are the usual failure.
  Test: category counts of user-confirmed findings across fixture reviews — instruction-clarity leads. Evidence: E-02 (the eight adj-20260723 lines), fable batches, fix-worthy clusters by rubric category: verification 29, instruction 19, trigger 13, grounding 9, economy 6, static 1 — on raw counts verification & safeguards leads, not instruction. Normalized per smell in the category (verification has 8 smells, instruction 5): instruction 3.8 vs verification 3.6 per smell — a narrow instruction lead. Top smells: MDT 11, MC 9, NVS/RL/MUR 6 each. The claim as stated is not confirmed on raw counts; category size confounds the comparison. Needs a pre-registered normalization rule before it can move either way.
- C09 [untested] Placeholder or dummy examples rot into debt; examples must be real and task-specific.
  Test: flag placeholder examples in fixtures; user confirms fix-worthiness; A/B later if cheap. Evidence: —

## From arXiv:2602.11619 (agent consistency study)

- C10 [untested] Consistency across repeated runs predicts correctness (paper: 32–55pp gap).
  Test: fixture evals with 5+ repeats; correlate run agreement with pass/fail. Evidence: —
- C11 [testing] Single-run evals flip verdicts; N runs + variance is the floor for any recorded score.
  Test: re-run a batch of single-run verdicts ×5; measure the flip rate. Evidence: E-01: finding-level flips 0/12 flaws for claude-fable-5 (both fixtures, pairwise Jaccard 1.0) but 2/12 for kimi-k3; score-level variance is real and concentrates in the probe-fed cold-reader dimension (range 2 across identical runs). E-06: flips 2/12 (fable) and 3/12 (kimi) on the deletion-heavy fixture — absences flip more than insertions ever did; and cold-reader ranged 2 again for fable even with the fixed question set, this time from probe answer sampling (one haiku run genuinely inverted a rule). A single run can misreport scores by 2 points and silently miss flaws in either family.
- C12 [untested] Divergence concentrates at the first real decision (paper: 69% at step 2), so trigger/when-to-use guidance deserves outsized review weight.
  Test: compare where eval trajectories diverge with strong vs weak trigger sections. Evidence: —
