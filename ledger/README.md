# ledger — run records

Every review commits one line to `runs.jsonl`. Append-only: a line is never edited or deleted. The only writer is `skills/review-skill/scripts/finalize.py` (D-015): the model authors a markdown report; the finalizer parses and validates it, extracts every evidence quote from the spans the report cites, runs the static checks, generates the machine facts, serializes with a JSON encoder, and commits. Never write or edit a line by hand, in any mode.

Schema v2 fields (one JSON object per line):

- `schema_version` — 2. Line 1 of runs.jsonl predates this schema (v1, hand-assembled, no schema_version field) — kept as history, never edited.
- `type` — `review`. Recall/precision from planted-fixture runs land later as `adjudication` lines referencing run_ids — `vs_manifest` in a review line is null at commit time because adjudication happens after the run.
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
