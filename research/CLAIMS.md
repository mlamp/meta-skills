# Claims register

Borrowed ideas are unproven here until our own evidence moves them. Status: untested | testing | validated | refuted. Every claim names the test that would move it. Evidence means our own records — ledger entries, fixture results, D-numbers — never "the paper says so".

Notes in research/notes/, PDFs in research/sources/. The harness that runs the tests: review-skill (D-009–D-013), planted fixtures under fixtures/planted/, records in ledger/runs.jsonl, queue in docs/experiments.md.

## From arXiv:2607.01456 (skill smells study)

- C01 [testing] The 26-smell catalog works as a review rubric for SKILL.md files — most hits are worth fixing.
  Test: run the smell checks on real fixtures; user spot-checks findings; survives if precision stays useful (~70%+). Evidence: E-01 (adj-20260721-aeea8221b2, -0beccec7a6, -b58423aa64): precision after user adjudication 1.0 / 0.969 / 1.0 per batch — 2 false positives across 15 runs. E-06 (adj-20260721-161797bfb1, -69d5d03b9a): precision 1.0 in all 10 runs of both families, including every absence-pass finding — the deliberate absence question added zero false positives. 25 runs cumulative, 2 fps total. Planted corpus only; the real-fixture spot-check (E-02) still has to run.
- C02 [testing] Smells are pervasive: real skills average ~10 smells, so near-zero hits means a broken detector, not a clean corpus.
  Test: median hits per file across 10+ real fixtures. Evidence: E-01 adjudication confirmed pre-existing smells in unmodified base text: 4 in the frontend-design base SKILL.md (TSW, ME, RL, BG), 1 in tdd's mocking.md (MDT). Direction agrees; the per-file median needs E-02.
- C03 [untested] The 13-component taxonomy covers what real SKILL.md bodies contain; usable as the structural vocabulary of review output.
  Test: classify fixtures' H2 sections against it; unclassifiable share stays low. Evidence: —
- C04 [untested] Descriptions shaped [what it does] + [when to use] + [keywords] trigger better than free-form ones.
  Test: A/B one skill with both description forms on trigger-worthy and distractor tasks, repeated runs; compare invocation precision/recall. Evidence: —
- C05 [untested] Bodies over ~5,000 words hurt outcomes (context bloat).
  Test: A/B a long skill vs its distilled variant on the same tasks. Evidence: —
- C06 [testing] An LLM judge can detect the semantic smells around F1 0.78 — good enough to pre-screen, not to auto-fail.
  Test: label a fixture subset ourselves; compute precision/recall for our judge, per model family. Evidence: E-01, pooled over the 18 planted semantic flaws: claude-fable-5 recall 0.778, precision 0.979, F1 ≈ 0.87 — every miss is a pure-deletion flaw; kimi-k3 on tdd-p1 F1 ≈ 0.98. E-06, deletion-heavy corpus (skill-creator-p1, 10 semantic plants, adj-20260721-161797bfb1/-69d5d03b9a): fable per-flaw recall 0.70, precision 1.0, F1 ≈ 0.82 — still above 0.78 with the absence pass; kimi 0.54 / 1.0, F1 ≈ 0.70 — first below-paper number, concentrated on absences outside SKILL.md and judgment plants. Deletion recall specifically: fable 0/4 in E-01 → union 6/8 in E-06; kimi untested → 4/8.
- C07 [untested] Smells persist once introduced unless deliberately fixed.
  Test: version-pair fixtures in fixtures/real/ (review old vs current snapshots); later, our own skills' git history. Evidence: —

## From arXiv:2509.20497 (prompt debt study)

- C08 [untested] Instruction-style text is the biggest debt magnet; clarity and length are the usual failure.
  Test: category counts of user-confirmed findings across fixture reviews — instruction-clarity leads. Evidence: —
- C09 [untested] Placeholder or dummy examples rot into debt; examples must be real and task-specific.
  Test: flag placeholder examples in fixtures; user confirms fix-worthiness; A/B later if cheap. Evidence: —

## From arXiv:2602.11619 (agent consistency study)

- C10 [untested] Consistency across repeated runs predicts correctness (paper: 32–55pp gap).
  Test: fixture evals with 5+ repeats; correlate run agreement with pass/fail. Evidence: —
- C11 [testing] Single-run evals flip verdicts; N runs + variance is the floor for any recorded score.
  Test: re-run a batch of single-run verdicts ×5; measure the flip rate. Evidence: E-01: finding-level flips 0/12 flaws for claude-fable-5 (both fixtures, pairwise Jaccard 1.0) but 2/12 for kimi-k3; score-level variance is real and concentrates in the probe-fed cold-reader dimension (range 2 across identical runs). E-06: flips 2/12 (fable) and 3/12 (kimi) on the deletion-heavy fixture — absences flip more than insertions ever did; and cold-reader ranged 2 again for fable even with the fixed question set, this time from probe answer sampling (one haiku run genuinely inverted a rule). A single run can misreport scores by 2 points and silently miss flaws in either family.
- C12 [untested] Divergence concentrates at the first real decision (paper: 69% at step 2), so trigger/when-to-use guidance deserves outsized review weight.
  Test: compare where eval trajectories diverge with strong vs weak trigger sections. Evidence: —
