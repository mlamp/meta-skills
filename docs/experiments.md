# Experiment queue

Ordered. Each experiment names the claims it moves. Results land in ledger/runs.jsonl and move statuses in research/CLAIMS.md.

- E-01 · Planted-fixture eval batch. Run review-skill on fixtures/planted/tdd-p1 and frontend-design-p1, 5 repeats each; one batch repeated by a second model family, headless. Compute recall vs manifests, precision after adjudication, run-to-run agreement. Moves: C01, C06, C11.
- E-02 · Real-fixture reviews with user spot-check. All real/ snapshots, single batch each, findings adjudicated by the user. Moves: C01 (precision), C02 (median smells per file), C03 (H2 sections vs the 13-component taxonomy), C08 (finding-category counts).
- E-03 · Version-pair persistence. Compare findings across the six old/current snapshot pairs in fixtures/real/. Moves: C07.
- E-04 · Description A/B. One skill, C04-form description vs free-form, trigger-worthy and distractor tasks, repeated runs; compare invocation precision/recall. Moves: C04, and C12 partially.
- E-05 · Long-vs-distilled A/B. skill-creator 2026-04-20-b9e19e6 is the corpus's only LSB fail (5,151 words). Distill it; run both variants on the same tasks. Moves: C05.
