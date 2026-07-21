# Claims register

Borrowed ideas are unproven here until our own evidence moves them. Status: untested | testing | validated | refuted. Every claim names the test that would move it. Evidence means our own records — ledger entries, fixture results, D-numbers — never "the paper says so".

Notes in research/notes/, PDFs in research/sources/.

## From arXiv:2607.01456 (skill smells study)

- C01 [untested] The 26-smell catalog works as a review rubric for SKILL.md files — most hits are worth fixing.
  Test: run the smell checks on real fixtures; user spot-checks findings; survives if precision stays useful (~70%+). Evidence: —
- C02 [untested] Smells are pervasive: real skills average ~10 smells, so near-zero hits means a broken detector, not a clean corpus.
  Test: median hits per file across 10+ real fixtures. Evidence: —
- C03 [untested] The 13-component taxonomy covers what real SKILL.md bodies contain; usable as the structural vocabulary of review output.
  Test: classify fixtures' H2 sections against it; unclassifiable share stays low. Evidence: —
- C04 [untested] Descriptions shaped [what it does] + [when to use] + [keywords] trigger better than free-form ones.
  Test: A/B one skill with both description forms on trigger-worthy and distractor tasks, repeated runs; compare invocation precision/recall. Evidence: —
- C05 [untested] Bodies over ~5,000 words hurt outcomes (context bloat).
  Test: A/B a long skill vs its distilled variant on the same tasks. Evidence: —
- C06 [untested] An LLM judge can detect the semantic smells around F1 0.78 — good enough to pre-screen, not to auto-fail.
  Test: label a fixture subset ourselves; compute precision/recall for our judge, per model family. Evidence: —
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
- C11 [untested] Single-run evals flip verdicts; N runs + variance is the floor for any recorded score.
  Test: re-run a batch of single-run verdicts ×5; measure the flip rate. Evidence: —
- C12 [untested] Divergence concentrates at the first real decision (paper: 69% at step 2), so trigger/when-to-use guidance deserves outsized review weight.
  Test: compare where eval trajectories diverge with strong vs weak trigger sections. Evidence: —
