# ledger — run records

Every run recorded in the ledger commits one line to `runs.jsonl`. Append-only: a line is never edited or deleted. Review lines are written only by `skills/review-skill/scripts/finalize.py` (D-015): the model authors a markdown report; the finalizer parses and validates it, extracts every evidence quote from the spans the report cites, runs the static checks, generates the machine facts, serializes with a JSON encoder, and commits. Adjudication lines are written only by `ledger/adjudicate.py` (D-017). Generation and experiment lines are written only by their documented skill or experiment harness. Never write or edit a line by hand, in any mode.

Schema v2 fields (one JSON object per line):

- `schema_version` — 2. Line 1 of runs.jsonl predates this schema (v1, hand-assembled, no schema_version field) — kept as history, never edited.
- `type` — `review`, `adjudication`, `generation`, or `experiment`. Measured `experiment` lines use `experiment: E-xx`, carry per-arm or per-task statistics and artifact hash pins, and are evidence candidates under D-023. E-09 cold-reader gate records use the composite discriminator `experiment: E-09-cold-reader` plus `tier: smoke | qualification`. They are gate context, not measured results: consumers must exclude them from claim, score, and experiment-effect aggregates. The four existing `tier: smoke` rows predate the repeatable-smoke protocol and remain append-only; current smokes write no ledger rows. Qualification rows may be written by the E-09 harness. Recall/precision from planted-fixture runs land as `adjudication` lines referencing run_ids — `vs_manifest` in a review line is null at commit time because adjudication happens after the run. An adjudication line (written by `ledger/adjudicate.py`, D-017) carries: `batch_id`, `run_ids`, `manifest_sha256_16`, `spans_sha256_16`, `per_flaw` catch rates, `recall` and `precision` (per-run, mean, min, max, stdev; recall also union), `agreement` (pairwise Jaccard, flaw flips, missed-all), `score_stats` per dimension, and every `adjudications` verdict (`flaw:<n>` near-credit | `pre-existing` | `fp`).
- Real-fixture batches have no manifest, so no auto-match and no recall. Their verdicts land as adjudication lines with `mode: "spot-check"`, written only by `adjudicate.py spot-commit` (E-02 protocol). Every finding in the batch is clustered deterministically (same smell + same file + overlapping spans, ±2 lines); the user verdicts each cluster `fix-worthy | not-fix-worthy | wrong-evidence`. Strict precision counts fix-worthy alone as a true positive; grounded precision also counts not-fix-worthy. The line carries every verdict with full cluster membership (run + finding index), per-run and pooled precision at finding and cluster level, agreement stats over cluster sets, score variance, confirmed counts by file/smell/category, clustering parameters with pad-sensitivity counts, and the worksheet hash. Recall and manifest fields are absent, never zero. One live spot-check line per batch: a correction is a new line naming the old one in `supersedes`, never an edit.
- A `generation` line records one agent-voice run and is written only by `skills/agent-voice/scripts/finalize.py` (D-021): target project, files written with `sha256_16`, the choices made (sections, activation scope, settings routed), probe result, notes. Minimal by design; it grows when real runs show what matters (pattern of D-006).
- `run_id` — `r-YYYYMMDD-<10 hex>`, content-addressed (hash over payload + batch id + seq): an identical re-run dedupes; legitimate repeats in a batch differ by seq and don't collide.
- `batch_id`, `batch_seq` — assigned by the eval harness; solo runs default to `b-YYYYMMDD-solo`, seq 1.
- `date` — ISO 8601, from the script's clock, never the model.
- `target` — `{path, files_sha256_16}`: hash prefixes of the exact bytes evidence was extracted from.
- `reviewer` — `{skill, version_sha (+dirty when uncommitted), model, effort}`; sha from git, model/effort from the report headers.
- `repeats_in_batch` — declared batch size; `1` means ad-hoc.
- `omitted_findings` — greater than zero means the model hit an output limit and said so; caps are never silent.
- `static` — check id → `{status, evidence, override?, reason?}`. A false-positive static fail keeps its raw result plus the model's drop reason — judgment is layered on the record, never replaces it.
- `findings` — `[{smell_id, location ("file:N-M", or "static" for auto-findings), evidence (extracted by the script from the cited span — transcription by the model is not a channel), blocker, why, fix, uncertain?}]`.
- `scores` — six dimensions, 1–4.
- `probe` — `{model, misreads}` or `{estimated: true}`.
- `vs_manifest` — null (see `type`).
- `notes` — free text.

Commit paths:

- Solo: direct append — O_APPEND single write + fsync; refuses a duplicate run_id, an unparseable existing line, or a ledger not ending in a newline.
- Batch: `--outbox` writes one validated file per run (atomic rename); the orchestrator's `--drain` is the only process that touches the shared ledger, re-validating each file and moving it to `committed/`. Parallel workers never append directly.

Rules (D-012): a score cited as evidence comes from a 5-run batch with variance (prior: C10/C11, untested). A line with `repeats_in_batch: 1` is context, never evidence.
