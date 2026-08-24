# E-09 design — catalog-assisted agent-voice interviews

Frozen before measured execution. This PR designs the experiment. It does not run it. Qualification and measured mode remain locked until `HEAD` equals the commit that last changed `freeze.json` and that commit is contained in `origin/main`. Measured mode also requires both cold-reader profiles to pass the current qualification suite.

## Question

Does adding the six U01–U06 recognition prompts to the current agent-voice interview improve discovery and downstream behavior without bloating the contract, selecting irrelevant patterns, or moving the same habit into substitute phrases?

E-09 screens C19–C22. Five runs are a screening batch, not a significance test. Results stay separate by model family.

## Frozen artifacts

- `catalog.json` owns the six candidate prompts, boundaries, sublabels, and overlap order.
- `persona-stage1.json` is the no-context extraction used to build the simulated user.
- `persona.json` owns source hashes, relevance, catalog mappings, and curator resolutions.
- `prompts.json` owns the shared observations, the one arm-specific insertion slot, and judge instructions.
- `tasks.json` owns four downstream tasks and their success rubrics.
- `substitutes.json` owns listed matchers, substitute matchers, precedence, and judge buckets.
- `cold_reader_cases.json` owns the qualification and disjoint smoke cases.
- `models.json` owns model roles and provider controls.
- `artifact-spec.json` owns the repository identity, release names, credential names, and pack-time sanitizer patterns.
- `../artifacts.py` owns deterministic packing and local, draft, published-release, digest, member, tag, and attestation verification.
- `../test_artifacts.py` owns the generic artifact regression tests.
- `harness.py` owns prompts, calls, retries, arithmetic, timestamps, hashes, IDs, and ledger serialization.
- `test_harness.py` owns the deterministic regression tests.
- `reviews.md` records independent design, implementation, and cold-reader reviews as context.
- `../../.github/workflows/verify-experiment-artifacts.yml` owns the read-only CI verification path.
- `freeze.json` pins every file above and this design. It does not hash itself.

No execution-time choice may change these bytes. A change creates a new freeze and invalidates prior qualification.

## Independent design work

Fable 5 xhigh and GPT-5.6 Sol xhigh proposed cold-reader cases independently. The frozen suite keeps GPT's five composite-case shape and Fable's emphasis on boundaries and exact identity checks. Both model outputs were advice, not evidence.

Fable 5 xhigh and Kimi K3 reviewed the experiment plan twice. Their accepted findings are reflected below: independent relevance curation, paired conditions, fixed zero rules, a contract cap, exact channel parity, seeded interleaving, conservative rates, duplicate judge passes, and loud qualification failures. Their final complete-diff review is recorded in this directory before freeze.

## Simulated user

The source population is the user's voice guidance written before 2026-08-21:

- `skills/agent-voice/references/contract-template.md`
- `docs/communication-contracts.md`
- `research/notes/disler-fixing-smartass-opus-5.md`

`persona.json` pins each source hash.

Construction had two stages.

1. Exact Haiku `claude-haiku-4-5-20251001` saw only those source bytes with no session context. It extracted V01–V10, an unaided-recall list, inventory choices, and limits. It did not see the unslop note, this experiment, D-029, or C19–C22.
2. Fable 5 xhigh and GPT-5.6 Sol xhigh mapped the frozen V rows to the catalog. Before either mapping, a human curator fixed relevance and preference rejection. After both proposals, the curator confirmed every row and resolved every disagreement. A positive catalog boundary alone did not count as a mapping.

`preference_rejected` belongs to the user in both arms. `mapping_confirmed` belongs only to catalog analysis. They are separate fields. A relevant preference that maps to no U ID remains in the answer key.

The manifest has nine relevant V preferences. V10 is independently rejected because reference codes are opt-in and the inventory selects no opt-ins. The relevant catalog IDs are U01, U03, U05, and U06.

## Arms

Both arms receive the same model instruction, inventory, unaided recall, latent observations, 60-token cap, contract format, and tool schema for evidence-linked rules. Neutral I01–I04 and O01–O09 IDs let both models cite the exact shared evidence without seeing the V answer key.

- Control receives the fixed text: no catalog was offered.
- Treatment receives only the U01–U06 catalog. This entire addition occupies one arm-specific insertion slot.

The shared observations contain all natural evidence used by either arm. Treatment receives labels and boundaries, not new incidents, confirmations, rejections, or corrections. This allows control to infer the same preferences and prevents the scored U set from entering the treatment prompt.

The control submission tool has no catalog fields or U IDs. The treatment tool adds the catalog selection fields. That schema difference is part of catalog availability. It prevents the control arm from learning the catalog through an output format.

Only selected evidence rows and selected treatment catalog IDs may own a rendered rule. Treatment automatic bans must be empty. Selected and rejected catalog sets must be disjoint; a rejected ID never receives selection credit. Unselected and rejected IDs must not reach the contract. Ignoring Markdown punctuation, the contract's lexical tokens must equal the ordered rule-text tokens exactly; extra, missing, duplicated, or reordered contract prose is a contract violation.

## Interview and contract protocol

One fresh model call performs the one-round interview interpretation and contract generation. It receives the frozen transcript rather than conducting an open-ended multi-turn conversation. This removes question-order and simulated-user branching from the comparison.

The model must call one typed submission tool. Claude-family profiles use the CLI's provider-enforced `StructuredOutput` tool; DeepInfra uses the required `submit_evaluation` function tool. The arguments contain selected IDs, source-linked rules, and the rules-only Markdown contract. Prose JSON is not accepted. The harness validates the arguments again after the provider validates the tool call.

The contract may contain at most 60 lexical tokens after fixed boilerplate is removed. The harness uses `\b[\w'-]+\b` over the returned contract body. An over-cap interview still contributes its proposed IDs to C19 and the over-cap count. Its contract is excluded from downstream execution. C20's density numerator counts only relevant IDs whose rules were rendered. An arm does not get credit for an over-cap proposal it could not use.

If the contract has zero lexical tokens, coverage density is 0. The trial still contributes task failures, irrelevant selections, and error counts. This rule applies to both arms.

## Model families and provider controls

The measured interviewer and downstream generator families are:

- `fable-subject`: `claude-fable-5`, high effort.
- `kimi-subject`: requested and reported `k3[1m]`, high effort.

Each call records the requested model, every provider-reported model, usage, start time, completion time, and any cache counters the provider supplies. Claude, Kimi, Haiku, and DeepSeek must include the required primary identity; a mismatch or missing echo is an error. Claude CLI may also report the exact pinned Haiku model used for auxiliary session metadata, which is recorded but not treated as the routed response model. Any other auxiliary identity fails. Codex JSONL does not echo the routed model, so GPT judge identity evidence is the requested model plus the recorded CLI version. There is no automatic model fallback.

Before any raw record is written, the harness sanitizes recognized secret and host metadata. It removes credential-bearing fields, redacts API-key assignments and bearer values, and removes or redacts host paths and session identifiers. No smoke artifact may be committed unless a second sanitizer pass makes no change and an exact-value scan finds none of the locally configured credentials. The exact-value scan compares stored text against nonempty credential values loaded from the ignored `.env` file and current environment; it never records those values. This catches secrets whose surrounding text has no recognized pattern. If either check fails, keep the artifact local, extend the sanitizer, produce a new smoke attempt, and rerun both checks. If that cannot be done safely, stop and leave the artifact uncommitted.

The CLI does not replace each provider's hidden base system prompt. The experiment is therefore a CLI-prompted comparison, not a raw-model API comparison. Every task condition uses the same `--append-system-prompt-file` channel. The no-suppression condition passes the same boilerplate plus any evidence-only rules through that channel.

Every CLI call uses a fresh temporary working directory, safe mode, no resume, no session persistence, and an explicit effort. Text calls have no tools. Structured Claude-family calls expose only the CLI's provider-enforced `StructuredOutput` tool. Safe mode removes user and project instructions, settings, skills, plugins, hooks, and custom MCP servers while preserving CLI authentication. Haiku runs at low effort. Sampling controls unavailable in a provider wrapper are recorded as `provider_default_unsettable`, not guessed.

The local `claude-kimi` wrapper owns slot selection and may retry once on another slot before returning a rate-limit or authentication failure. The harness records the final slot file, wrapper stderr, and each outer harness attempt. The wrapper does not expose a separate structured record for an internal failed slot, so E-09 cannot claim per-slot attempt accounting.

The blinded judge is GPT-5.6 Sol at high effort through structured output. It is a third family. Its task judgments and substitute judgments never receive arm, subject family, or repetition metadata.

## Repetitions and schedule

There are five independent runs per arm and family:

- 2 families × 2 arms × 5 repetitions = 20 interview calls.
- Each usable contract runs 4 suppression tasks.
- Treatment contracts also run the same 4 tasks after their catalog-linked rules are removed. Maximum downstream calls: 10 control contracts × 4 plus 10 treatment contracts × 8 = 120.

Seed `20260821` fixes one interleaved family × arm × repetition interview order. The same seed fixes downstream job order. Seed `20260822` fixes judge order. The harness prints the schedule before execution and records actual timestamps. It never groups one arm first.

All planned calls are started even when earlier calls fail. Before each measured provider call, the harness appends its path to the measured record manifest. After the immutable record is written, it appends the record hash. An operator interruption resumes the same content-addressed namespace and skips only records whose hashes still match. A started, missing, changed, or incompletely recorded call blocks the freeze instead of being rerun. There is no result-based early stop, extra repetition, silent restart, or optional continuation.

## Downstream tasks

`tasks.json` freezes four discriminating tasks:

- T01 rejects Redis for a single-process, one-writer desktop store and names a restore path.
- T02 diagnoses the explicit missing `name` field and verifies the fix.
- T03 reports exactly the two stated retry and secret-logging defects.
- T04 states the imported catalog's unproven status and local evidence threshold.

The subject family that generated a contract also answers its downstream tasks. The contract is attached through the same system-prompt channel for both families and conditions.

For each treatment contract, suppression and no suppression form a pair. The no-suppression renderer removes only rules whose treatment tool record names a selected catalog ID. It keeps every evidence-only rule and uses the same boilerplate and channel. The selected tic set, task, generator, repetition, and other contract rules remain fixed within the pair. Control has no catalog-linked rule field and therefore runs only the suppression condition; C21 uses the five treatment pairs per family. The harness records removed rule and lexical-token counts per pair. A pair with no removed catalog-linked rule has no suppression contrast and makes C21 incomplete.

## Cold-reader qualification

The qualification checks whether cheap readers understand the catalog before its wording can bind the measured treatment arm.

Required profiles:

- exact Haiku `claude-haiku-4-5-20251001` at low effort;
- DeepSeek `deepseek-ai/DeepSeek-V4-Flash-0731` through DeepInfra's OpenAI-compatible endpoint. No reasoning override is sent.

Each case is a fresh call. The model must use one required typed submission tool. Its arguments have a case-specific JSON Schema. This isolates semantic comprehension from JSON formatting skill. Missing, duplicate, invalid, or prose-only submissions fail the case and are not retried. A qualification attempt key binds the freeze, reader name, full reader profile, harness, catalog, and suite hashes; smoke uses the same semantic-input hashes without a freeze dependency.

The five composite cases cover:

- C0: recognition-only status, selected-only routing, no automatic bans, precedence, and every sublabel;
- C1: ten positive spans covering every ID and sublabel;
- C2: eight boundary negatives;
- C3: three overlaps whose winner depends on U01–U06 precedence;
- C4: positive selection, explicit rejection, automatic-ban rejection, and select-none.

Tool arrays are graded as sets unless order carries meaning. Precedence is graded in exact order. Missing or extra fields fail schema validation. The answer key never enters the model prompt or tool schema.

Qualification is five repetitions per required profile. Every assertion must pass in all five repetitions in both families. There is one batch attempt per exact freeze, catalog, case-suite, reader-profile, and harness hash set. An exclusive start marker consumes the attempt before the first call, so an interruption cannot restart or overwrite it. A completed failed batch is immutable and ledgered. Summary finalization derives one stable run ID from the exact row fields, counts, raw path, key, and canonical `completed_at`; it excludes only `run_id` and `date` from that content digest. It writes that ID into the summary, then ensures the exact ledger row: create it if missing, accept an existing row only when its canonical JSON matches, and reject the same ID with different content. The qualification and measured gates use the same field set to rederive the ID and restore whichever side of an interrupted finalization is missing. They never repeat provider calls during that repair. For a new row, the trusted verifier independently derives the same exact row shape, counts, current input hashes, path, timestamp, pass state, and run id. The append-only trusted baseline preserves older qualification rows after those input bytes change; the verifier checks their self-consistent shape and identity without treating them as current. A rerun requires a real byte change to an input bound by that attempt key. Formatting failure blocks the gate deliberately.

Qualification can start only when `freeze.json` matches, `HEAD` equals the commit that last changed it, that commit is contained in `origin/main`, and the tree is clean apart from current immutable qualification records. The attempt key also binds the freeze hash. Its pass is context for binding-text comprehension, not evidence for C19–C22.

`cold_reader_cases.json` also contains a disjoint M01–M02 smoke catalog. Smoke runs prove only the adapters, tool schema, raw isolation, and grading path. They never see U01–U06 cases and never count as evidence.

Smoke history has two formats:

- Legacy: four reader smokes ran before the repeatable protocol existed. This PR only preserves their historical ledger rows and raw artifacts alongside current attempts. Each summary sits directly under `raw/smoke/cr-<id>/`, carries `ledger_run_id`, and remains append-only `tier: smoke` context. Qualification and measured gates ignore these runs.
- Current: the harness writes every new reader or adapter smoke beneath `attempt-NNN`. It neither appends a ledger row nor puts `ledger_run_id` in the summary. Attempts may repeat. Only the latest attempt controls the smoke gate. A failed latest attempt blocks qualification until a newer attempt passes. For each reader profile, exactly one qualification batch may run per exact freeze, catalog, suite, profile, and harness key, and it may start only after that reader's latest current smoke passes.

The smoke schemas must exercise every structured-output keyword used later, including fixed array sizes, `uniqueItems`, nullable enums, and `minLength`.

Before measured execution, `adapter-smoke` must also pass for every measured path: Fable tool and text, Kimi tool and text, and GPT structured judgment. It uses only M01–M02 and `SMOKE_OK`, records exact reported identities or the documented Codex CLI limitation, and is keyed by the harness, model registry, and prompt hashes.

## Metrics

The harness reports every per-run value, mean, sample variance with denominator `n-1`, and sample standard deviation. It does not pool model families. Finalization first verifies the published immutable raw bundle from a fresh download. It then writes `results/<measured-id>.json` before idempotently ensuring its two stable run IDs in the ledger. A rerun can finish an interrupted append but cannot create different or duplicate results.

### Interview metrics

- Selected-pattern coverage = relevant U IDs selected / 4 relevant U IDs.
- Selection precision = relevant selected U IDs / all selected U IDs. A select-none run has precision 1 and coverage 0.
- Selected count = number of relevant U IDs proposed, including an over-cap interview.
- Contract size = lexical tokens and words after fixed boilerplate. The current tokenizer is the frozen lexical regex; both reported names use that count.
- Contract coverage density = 100 × relevant rendered U IDs / contract lexical tokens. It is 0 for a zero-token or over-cap contract.
- Irrelevant selections = selected IDs outside U01, U03, U05, and U06.
- Over-cap = contract body exceeds 60 lexical tokens.

An evidence selection maps through the frozen evidence-to-V table and then the curator-fixed V-to-U table in `persona.json`. A treatment U selection joins that set. Each U ID counts once. An over-cap ID can affect C19 selected count but not C20 rendered density.

### Downstream metrics

- Task success = all required rubric rows present and no fatal row present.
- Task failures per trial = 4 minus successful suppression-condition tasks. An excluded, missing, timed-out, or unjudged task fails.
- Listed-tic hits = frozen deterministic matcher spans after overlap precedence.
- Listed-tic rate = 1,000 × total listed hits / total lexical output tokens across the four tasks in one trial.
- Substitute-tic raw count = confirmed adjacent substitute spans for the trial's user-selected U IDs across the same four tasks. Confirmed candidates outside that set are reported separately and do not enter C21.
- Substitute-tic rate = 1,000 × confirmed substitute spans / total lexical output tokens.

C22's rate is conservative when treatment shortens output. Raw listed hits and total tokens are always reported beside it.

A trial rate is undefined when its four tasks return zero lexical tokens. Undefined rates are excluded from the mean, their errors remain explicit, and the claim screen cannot pass unless all five rates exist. The report also gives pooled hits, pooled tokens, and their rate for context.

## Matchers and substitute adjudication

`substitutes.json` closes both vocabularies before output exists. Listed and substitute regex sets are disjoint. Matching is case-insensitive over final downstream responses. An overlapping span belongs to the first matching U ID in U01–U06 order.

The harness creates blind substitute candidates from the frozen substitute regexes. GPT judges the same candidate set twice with the same schema and no arm metadata. The report includes judge agreement. Identical raw outputs are retained as five observations and marked as zero observed variance; the harness does not invent an effective sample size.

A disagreement goes to the frozen human-adjudication sheet by blind candidate ID. The curator sees response context and taxonomy, but not arm, family, or repetition. No C21 metric is computed until every disagreement is resolved.

Report confirmed substitutes in three descriptive buckets:

- unaided-only: the mapped U ID was selected only through shared inventory or observation evidence;
- catalog-mapped-only: it was selected only through a treatment U field;
- both: both routes selected it.

These buckets do not change the primary count.

## Errors, retries, and exclusions

- A transport error or provider 5xx/429 gets one retry after the same prompt and configuration. Both attempts are recorded.
- A timeout is a transport error.
- A schema, tool-call, identity, or parsing failure gets no retry. It is a formatting error.
- A provider 4xx other than 429 gets no retry.
- A missing interview is an error and contributes no selected IDs. Its four tasks are failures.
- An over-cap contract is excluded from downstream calls. Its four tasks are failures. Its proposed selection remains visible for C19 and over-cap reporting.
- A contract is also excluded when a rendered rule cites unselected or rejected evidence, cites an unselected or rejected catalog ID, exposes internal V/U IDs, has no source, is missing from the contract under lexical-token comparison, or declares an automatic ban. The proposed selections remain visible; the four suppression tasks fail.
- A missing, timed-out, formatting-failed, or unjudged downstream call is a task failure. It contributes zero observed tic hits and zero output tokens, and its error remains explicit. A trial with no returned text has an undefined rate, never a zero rate; error counts sit beside every rate.
- No run is silently replaced. A provider outage becomes recorded transport failures and the fixed schedule continues.

Error and exclusion counts are reported by arm and family. The planned denominator remains five.

## Raw records and blinding

Raw paths are content-addressed by the frozen files.

```text
experiments/e09/raw/
  smoke/cr-<hash>/attempt-<n>/...
  smoke/adapters/as-<hash>/attempt-<n>/...
  qualification/cr-<hash>/...
  measured/m-<freeze-hash>/
    metadata.json
    interviews/<family>/<arm>/rep-<n>.json
    tasks/<family>/<arm>/rep-<n>/<condition>/<task>.json
    judgments/task/<blind-id>.json
    judgments/substitute/<blind-id>/pass-<n>.json
    adjudication-pending.json
```

Every provider call records its requested and reported identity, timing, attempts, usage, result, and error. An append-only measured call manifest records each call start and completed record hash. The packager verifies it. The harness owns all paths and timestamps. Prompts are reconstructed from frozen inputs; the hash of every input is in `freeze.json`.

Task and substitute judges receive only blind IDs, rubrics, candidate text, and needed response context. The key from blind ID to arm and family stays in the task raw path and is joined only during finalization.

## Raw artifact publication

`freeze_sha256` is the SHA-256 of the frozen `freeze.json` bytes. A compact result is a schema-2 object. Its `lines` array equals every and only ledger row whose `results_path` names that file. The packager never removes adjudication files. The operator removes a stale pair before rerunning blinded adjudication.

After all judgments and any blind human adjudication, `artifact-pack` derives the expected inventory from the frozen schedule and actual valid-task blind ids. It requires exactly 20 interviews and 120 task records. Every record's embedded family, arm, repetition, condition, task, blind id, pass, status, error, and attempt sequence must agree with its path and the frozen call protocol. Failed and excluded records cannot carry a result. Every record-manifest path must resolve to one regular file inside the measured namespace. Task and judge schedules are recomputed from the frozen seed and raw records. It also requires every corresponding task judgment and both substitute-judgment passes. `adjudication-pending.json` and `adjudication-resolved.json` must exist exactly when those passes disagree. The pending file must equal the current disagreement set. The resolved file must contain one valid verdict list for every and only current disagreement blind ID. An adjudication file is stale when either file exists without current disagreements or the pending file differs from them. Missing, stale, and extra files stop packaging.

The measured directory and local `.artifacts/` directory are ignored by Git. `artifact-pack` writes a deterministic archive, manifest, and local plan. `artifact-pack`, both release commands, and `finalize` require local `HEAD` equal to the exact frozen commit and require the current packager and every provenance file to match that commit byte for byte. `verify-local` checks only the archive and manifest. Frozen `freeze.json` supplies the complete provenance key set, and the artifact spec at that commit supplies the sanitizer policy. Before GitHub contact, `stage-release` and `publish-release` each independently run the frozen harness, derive a fresh plan, and require exact equality with the saved plan. Plan equality authenticates the expected execution, retries, exclusions, and inventory. Each command then separately requires the manifest and current raw inventory and member bytes to match its fresh derived plan. A raw change between the commands makes `publish-release` fail. A coordinated edit to the saved plan and manifest cannot change those values. The operator inspects the draft before running the separate publish command. Inventory includes every planned provider-call record, failed or excluded task record, judgment required by a valid task output, batch metadata, call manifest, and required adjudication record. Separate status counts preserve failures and exclusions. Before publication, expected and actual inventory must match, sanitization and digests must pass, and every error, retry, and exclusion must agree with the frozen protocol and raw records. Any unexplained outcome or sanitization match blocks. There is no waiver; correct the frozen input and start a new batch. The publish command requires the exact tag as confirmation. Before any GitHub contact, it rejects a conflicting tracked manifest. Before the irreversible publish action, it queries GitHub and rejects an existing tag that points away from the frozen commit. Publication copies the released manifest bytes unchanged to `artifacts/<measured-id>.json`. It does not delete the raw directory. Immediately after remote verification and again before it writes the compact result or ledger lines, finalization requires the current packager and provenance bytes to match the frozen commit and the current raw inventory and member bytes to match the derived plan and manifest. Trusted verifier code requires the complete E-09 result-row schema and the harness's canonical content-addressed run id. It rederives arm summaries, rates, paired differences, counts, and claim checks from five ordered run records, includes the canonical completion timestamp in the digest, and requires exactly one row for each frozen model family. The compact result must equal the complete ledger row set for its path, and every ledger row repeats the manifest's freeze hash. A changed freeze produces a new content-addressed measured id and namespace; it never reuses an earlier freeze's namespace.

`stage-release` checks the repository immutable-release setting through the GitHub API and refuses to create or resume a draft when it is disabled. Release and tag lookups are paginated and fail closed on an API error. Both release commands compare the repo-relative root, manifest fields, expected paths and kinds, expected counts, sanitizer policy and report, and every member's byte length and SHA-256 with the current plan and raw tree. They reject root or child symlinks, hard links, and cross-platform unsafe paths before any raw-tree read or write. Every JSON document and decoded nested JSON string must reject duplicate object keys and non-finite numbers. The sanitizer decodes nested JSON strings until exhausted and fails closed at its resource limit. The archive verifier reproduces the deterministic archive and requires exact bytes. Any mismatch exits nonzero before draft creation or publication. `publish-release` rechecks supersession, the frozen packager commit, and default-branch containment; publishes; waits for immutability; performs the first fresh-download and attestation verification; then copies the released manifest bytes into `artifacts/<measured-id>.json`. That automatic check is remote-verification stage six. The separate `finalize` command is stage seven and independently repeats the source, fresh-download, tag, member, and attestation checks before it writes `results/<measured-id>.json` or ledger lines. It requires exact repository, experiment, freeze, schedule, batch, and raw-root metadata; validates every successful interview, task, task-judgment, and substitute-judgment payload; and recomputes an existing compact result before accepting it on retry. Retry a transient or interrupted command only with identical inputs. A content or policy failure requires a new frozen batch. A wrong published bundle requires a new release whose manifest names the old tag in `supersedes`. Unpublished or abandoned work does not use `supersedes`.

## Measured gate

`interviews` refuses to start unless all conditions hold:

1. `freeze.json` matches every frozen file.
2. The worktree has no unrelated changes. The only allowed changes are smoke history, the current passing qualification namespaces, their exact rederived ledger appends, the current adapter-smoke namespace, this freeze's own resumable measured namespace, and this batch's exact committed artifact manifest and result paths. The gate regrades every frozen qualification case record and checks the complete namespace, start marker, summary, and derived row. Every required run id must appear in the current uncommitted ledger additions; a committed-only row cannot authorize measured calls. These local records are an integrity gate, not provider-signed proof against a hostile local writer.
3. `HEAD` equals the commit that last changed `freeze.json`, and that exact commit is contained in `origin/main`.
4. Both required reader profiles passed qualification for the exact current freeze, catalog, suite, reader-profile, and harness hashes.
5. Every measured adapter passed its current disjoint smoke path.
6. Before each measured phase can call a provider, the harness creates the exact measured namespace beneath the repository and rejects redirected parents, links, non-directory path components, or existing linked children. The namespace then either has no records or matches the same freeze metadata.

This issue and PR cannot produce measured evidence.

## Claim movement

No claim moves on a single run, a pilot, a qualification, pooled families, or advice from a reviewer. Every screen reports `pass`, `fail`, `incomplete`, or `not_testable`. Incomplete batches move no claim. A ceiling-blocked C19 batch is not testable by this transcript and is not a falsifier.

- C19 moves to testing evidence only if each family returns five valid interview submissions, the treatment mean relevant-selected count is at least one higher than control, and the control mean leaves room for a one-pattern gain. If the maximum possible gain is below one, C19 is `not_testable`; otherwise a complete gain below one fires its falsifier.
- C20 is complete only when all ten interview submissions and all their task judgments in a family are valid. Unjudged tasks remain reported as failures but cannot fire a claim falsifier. On a complete screen, C20 survives only if treatment coverage density is not lower, treatment median irrelevant selection is at most one, and treatment mean task failures exceed control by no more than one. Any failed clause then fires the falsifier.
- C21 is supported only if, in each family, all five pairs remove at least one catalog-linked rule and the suppression outputs have both a higher mean raw confirmed substitute count and a higher mean confirmed-substitute rate than their paired no-suppression outputs. A missing contrast or undefined rate is incomplete. On a complete screen, either quantity not being higher fires the falsifier. Raw counts, removed-rule counts, rates, paired differences, and judge agreement are reported.
- C22 is complete only when all ten interview submissions are valid and all ten per-trial listed-tic rates exist. It is supported only if treatment's mean listed-tic rate is lower than control. On a complete screen, otherwise its falsifier fires. Raw hits and token totals remain visible.

This five-run screen can move a claim from untested to testing or record a falsifier. It cannot by itself validate a claim.

## Known limits

- The scripted transcript measures recognition and prioritization under a fixed simulated user, not a live user's changing answers.
- The treatment includes a bundled procedure: catalog labels, boundaries, and catalog-specific selection fields. E-09 estimates that bundle. It cannot attribute a gain to one row or to labels separately from the structured selection step.
- Both subject families run through CLI base prompts. Results do not isolate raw foundation-model behavior.
- Four tasks cover diagnosis, design, constrained review, and status summary. They do not represent every coding-agent task.
- Deterministic surface matchers trade recall for pre-run stability. The duplicate blinded judge covers only the closed substitute candidates.
