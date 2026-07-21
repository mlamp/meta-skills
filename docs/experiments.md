# Experiment queue

Ordered. Each experiment names the claims it moves. Results land in ledger/runs.jsonl and move statuses in research/CLAIMS.md.

- E-01 · DONE 2026-07-21 · Planted-fixture eval batch. 15 runs, 3 batches, all committed through the outbox drain; 13 off-manifest clusters user-adjudicated. Results (ledger): adj-20260721-aeea8221b2 (tdd-p1 × claude-fable-5: recall 1.0 every run, precision 1.0, Jaccard 1.0), adj-20260721-0beccec7a6 (frontend-design-p1 × claude-fable-5: recall 0.667 every run — all four pure-deletion flaws missed by all runs, precision 0.969, Jaccard 1.0), adj-20260721-b58423aa64 (tdd-p1 × kimi-k3: recall mean 0.967 union 1.0, precision 1.0, flips TOB and BG). Moved C01, C02, C06, C11 to testing.
- E-02 · Real-fixture reviews with user spot-check. All real/ snapshots, single batch each, findings adjudicated by the user. Moves: C01 (precision), C02 (median smells per file), C03 (H2 sections vs the 13-component taxonomy), C08 (finding-category counts).
- E-03 · Version-pair persistence. Compare findings across the six old/current snapshot pairs in fixtures/real/. Moves: C07.
- E-04 · Description A/B. One skill, C04-form description vs free-form, trigger-worthy and distractor tasks, repeated runs; compare invocation precision/recall. Moves: C04, and C12 partially.
- E-05 · Long-vs-distilled A/B. skill-creator 2026-04-20-b9e19e6 is the corpus's only LSB fail (5,151 words). Distill it; run both variants on the same tasks. Moves: C05.

## Queued work from E-01 (found mid-eval, never patched mid-eval)

- Deletion blindness, the big one: every pure-deletion flaw was missed by every run (frontend-design-p1 flaws 5, 6, 10, 11 — fable-only batch; the MT deletion was caught only through its leftover vague sentence; no deletion flaws exist in tdd-p1, so the second family is untested on absences). The rubric checks what is present, not what the skill's job implies should exist. Candidate fix: per-dimension absence prompts in the judgment pass, and a deletion-heavy fixture for the second family.
- ME/MT boundary: the same deleted token spec was filed as ME by two runs and MT by three — smell-label instability on absences forced a near-match adjudication. Sharpen the counts/doesn't-count cues.
- Cold-reader is the noisiest dimension: score range 2 across identical tdd-p1 runs while every other dimension held within 1. Probe questions are improvised per run; standardize them or tighten the anchors.
- NTPD cue: an imperative inside the description was filed as NTPD twice, both uncertain. Clarify that imperative mood is not second person, or say it counts.
- static_checks.py reports BP/REF line numbers relative to the frontmatter-stripped body, not the file (off by the frontmatter length; noted by kimi-k3 seq 4).
- adjudicate.py: a worksheet row with an empty verdict loses its trailing tab under naive stripping; harden the parser.
