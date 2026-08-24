# E-09 design reviews

Reviewer advice is context, not evidence. Findings are adopted only when they identify a real validity or execution problem.

## Plan reviews

Fable 5 xhigh and Kimi K3 reviewed the neutral plan twice before implementation. The design records the accepted changes: relevance fixed before mapping, separate preference rejection and catalog mapping, a 60-token cap, zero-density rules, exact system-prompt channel parity, seeded interleaving, raw and normalized rates, duplicate substitute judgments, and frozen human adjudication.

## Complete-artifact review 1

Models: `claude-fable-5` xhigh and `k3[1m]` high. Both read the complete candidate independently on 2026-08-21.

Resolved material findings:

- Treatment named the relevant U IDs. Removed. Treatment now receives only the catalog and the same evidence as control.
- C0 asked which experiment arm could see the catalog, but the reader prompt did not state that. Removed the arm assertion. Catalog purpose is now explicit and arm-neutral.
- Selected IDs, not rendered rule sources, fed contract density. Corrected to rendered rule sources.
- Failed outputs could enter tic-rate means as zero. Zero-output rates are now undefined; claim screens require all five rates and report pooled totals.
- No-suppression used different, condition-revealing boilerplate and formatting. Both conditions now use one boilerplate and one rules renderer.
- Contract-violation exclusions were under-specified and used brittle substring matching. The design now lists them; the harness uses lexical token sequences and rejects automatic bans.
- Qualification could restart after interruption. An exclusive start marker now consumes the exact hash/profile attempt before the first call.
- T04 lacked the facts needed in an isolated task call. Its frozen prompt now contains the status brief to summarize.
- Judge order was not using its registered seed. It is now seeded and recorded.
- The measured clean-worktree gate blocked its own raw outputs. It now permits only current qualification artifacts, their exact ledger appends, and the content-addressed measured namespace.
- The freeze file had no owner command. The harness now writes it once and measured mode requires it.
- The U04 substitute regex could swallow later candidates. Its gaps are bounded.

Follow-up implementation checks:

- The disjoint measured-adapter smoke passed all five paths: Fable tool and text, Kimi tool and text, and GPT structured output.
- Judge transport errors remain judge errors. They cannot enter human disagreement resolution or become zero substitute rates.
- Kimi records its selected slot. Codex records its executable, CLI version, JSONL events, and usage; the CLI does not echo the routed model, and the design states that limit.
- Claude-family calls now reject provider error envelopes even when the process exits zero.

## Complete-artifact review 2

Models: `claude-fable-5` xhigh and `k3[1m]` high. Both independently read the complete candidate and the review-1 repair list on 2026-08-21.

Resolved material findings:

- Broad evidence mappings can put control near the four-pattern ceiling. The symmetric mapping stays frozen, but C19 now reports `not_testable` when control leaves less than one pattern of possible gain. It cannot record a ceiling-caused falsifier.
- Redundant judge booleans could disagree with their own row verdicts and block finalization. Task success is now derived only from rubric rows. Substitute status is now represented only by a nullable pattern ID. Candidate coverage and order are validated separately.
- The human disagreement sheet contained only blind IDs. It now includes the closed taxonomy, candidate text, response context, and both judge passes without arm, family, repetition, condition, or raw paths.
- The GPT smoke used a trivial schema. It now runs the real task-judge and substitute-judge schema shapes. The current smoke passed both.
- Failed and not-testable screens were conflated. Every claim now reports `pass`, `fail`, `incomplete`, or `not_testable`; missing rates and invalid interview submissions cannot become falsifiers.
- `judge` could freeze an incomplete schedule. It now requires all 120 task records before storing judge order.
- Smoke attempts were one-shot and ledgered like evidence. Reader and adapter smokes now use numbered attempts, write no ledger lines, and may be repeated. Qualification requires a current passing smoke for that reader.
- C21 did not verify that suppression removed anything. Each pair now reports removed rules and tokens; five nonempty contrasts are required for a complete C21 screen.
- Returned contract prose could differ from executed structured rules. Exact ordered lexical identity is now required.
- User Claude configuration could enter structured calls. Claude-family structured submissions now use the provider-enforced `StructuredOutput` tool under safe mode. Text calls also use safe mode. Fable, Kimi, and Haiku passed this path.
- Sublabel names lacked definitions. The rendered catalog now defines every sublabel before the exact cold-reader gate.
- Finalization could append new run IDs on a second invocation. It now writes immutable results first and idempotently ensures stable ledger lines.
- Uncommitted measured records could be deleted and silently regenerated. A start/completion manifest now records each provider-call path and hash. Missing, changed, or incomplete records block the freeze.

Two recommendations were resolved differently from their suggested implementation:

- Unexpected harness faults remain fail-closed. They are recorded and make resume require a corrected freeze; the harness does not retry because the failed code path may already have consumed a provider call.
- The broad evidence mapping was not replaced by another model judge. A blinded semantic scorer would add a second treatment-sensitive measurement layer. The explicit ceiling status preserves the symmetric frozen answer key and states when C19 cannot answer its question.
- Four smoke lines written before the repeatable-smoke protocol remain in the append-only ledger. They are explicitly `tier: smoke`, are not evidence, and their legacy raw paths are ignored by current gates.

Provider correction found during smoke:

- The DeepSeek credential belongs to DeepInfra, not DeepSeek's first-party endpoint. The profile now uses `https://api.deepinfra.com/v1/openai` and exact model `deepseek-ai/DeepSeek-V4-Flash-0731`. Preflight found the model and the typed-tool smoke passed 6/6.

## Final repair verification

Fable 5 xhigh and Kimi K3 independently reread the repaired artifact set. Kimi reported no material validity or execution blocker. Fable found four remaining gaps; all were resolved before freeze:

- Required smoke history was not allowed by the qualification and measured worktree gates. Both gates now allow the non-evidence `raw/smoke/` prefix while still requiring the latest current attempts to pass.
- Exact contract/rule identity was enforced but not stated to the interviewer. The shared format now forbids headings and requires exactly the ordered `rules[].text` values, one per line.
- A task-judge error could make C20 fail. C20 is now incomplete unless every task judgment exists and is valid; the failure metric remains visible.
- Legacy smoke records appeared to contradict the new no-ledger rule. They remain because the repository ledger is append-only. The design now labels the four lines and non-numbered directories as pre-protocol context ignored by current gates.

Fable also noted that the smoke schema had not exercised `uniqueItems` or `minLength`; the current disjoint smoke now covers both. Kimi noted that the ledger allowlist checked only unstaged changes. It now compares the ledger against `HEAD`, covering staged and unstaged changes, and both worktree gates print the offending status lines.

Both reviews were advice, not evidence. All accepted findings were fixed in the design, harness, tests, or frozen records rather than copied verbatim.

## Pull-request review repair

Copilot found that `append_jsonl` searched for raw run-ID bytes instead of comparing the decoded `run_id` field. An ID mentioned in another field could therefore block a valid append, and a record without `run_id` could reach a `KeyError`.

The harness now parses each existing JSONL object, requires a non-empty string `run_id`, and compares that field exactly. The cold-reader ledger pre-check uses the same parser. Regression tests cover exact duplicates, unrelated-field substrings, missing new IDs, and missing IDs in existing rows. The then-current test suite passed. Fresh Haiku and DeepSeek smokes passed 6/6, and all six Fable, Kimi, and GPT adapter paths passed on the repaired harness hash.

Copilot's next full pass found that committed Claude and Codex metadata carried absolute workstation paths and session identifiers. The harness now drops host-only event fields, reduces executable paths to basenames, and redacts embedded home or temporary paths before writing any record. A follow-up pass found session UUIDs inside JSON-encoded legacy Warp notifications, so string sanitization now redacts UUID-shaped identifiers too. The same sanitizer was applied to the four ledger-linked legacy smoke namespaces. Two regression tests enforce the sanitizer and scan every retained smoke JSON file for portability. The then-current 49-test suite passed. Fresh Haiku and DeepSeek smokes passed 6/6, and all six adapter paths passed with privacy-safe records.

A later pass found that a design-PR regression test failed whenever legitimate measured outputs existed in the checkout. The replacement tests the durable boundary instead: `freeze.json` may contain design inputs, but no raw run output or ledger state. It does not inspect local run directories.

Copilot then read the four committed legacy smoke rows as output from the current harness. The implementation was already correct: repeatable smoke attempts are numbered and unledgered. The design now separates legacy and current formats, paths, fields, and gate behavior. A fresh Claude Haiku 4.5 process with no project settings, tools, or session context correctly restated those obligations and found no contradiction. Its remaining questions concerned enforcement defined elsewhere in the design.

The next pass found a shorthand source name in the stage-1 persona provenance. Every `source_evidence` entry now starts with an exact path from the frozen `source_artifacts` list. A regression test checks the path, separator, and nonempty evidence text for every entry. All 50 tests pass.

Copilot then found that the artifact scan checked one obsolete environment-variable name but not credential values, and that qualification could stop after a ledger append but before persisting `ledger_run_id`. The sanitizer now removes secret-bearing fields and redacts API-key assignments and bearer values before write. The committed-artifact test reruns the sanitizer and compares stored text against credential-like values from the ignored `.env` file and current environment without logging those values.

Qualification now derives its run ID from explicit immutable summary fields, persists the ID, and idempotently ensures the matching ledger row. Both gates reconcile summary-first and ledger-first interruption states without repeating a provider call. A regression simulates both crash windows. All 51 tests pass. A fresh Claude Haiku 4.5 process with no project settings, tools, or session context correctly restated the privacy gate, collision behavior, and no-provider-call repair rule.

Fresh Haiku and DeepSeek reader smokes passed 6/6 on harness hash `223628db1b4e`. Fable and Kimi tool and text paths plus both GPT judgment schemas passed on the same hash. The 51-test suite passed again after adding those artifacts.

Copilot's next pass found a tautological zero-density test and an undocumented ledger subtype. Finalization and the test now share one `coverage_per_100_contract_tokens` helper. D-031 and `ledger/README.md` distinguish measured `E-xx` results from `E-09-cold-reader` gate context and require consumers to exclude the latter from evidence and effect aggregates. The qualification regression also asserts the composite `experiment` plus `tier` discriminator. A fresh Claude Haiku 4.5 process correctly restated the consumer and writer obligations with no project settings, tools, or session context.

The helper change produced final harness hash `8ca20ec1b8a7`. Fresh Haiku and DeepSeek reader smokes passed 6/6, and all six Fable, Kimi, and GPT adapter paths passed on that hash.

Copilot then found that non-OK task outputs were skipped without increasing `task_judge_errors`, so C20 could appear complete. Production now counts missing outputs, task errors, missing judgments, and judge errors through one tested helper. A missing task output also makes C21 substitute judgment incomplete and C22's listed-tic rate undefined. The ledger introduction now says "every run recorded in the ledger," preserving the explicit unledgered-smoke rule. All 52 tests pass.

Fresh Haiku and DeepSeek reader smokes passed 6/6 on repaired harness hash `7578ed0ec1b1`. All six Fable, Kimi, and GPT adapter paths passed on the same hash.

Copilot's next pass found that smoke namespaces claimed the U01–U06 catalog hash even though their prompts use the disjoint M01–M02 catalog. One renderer now owns both the smoke prompt and its hash. The regression requires smoke to hash that rendered catalog, requires qualification to keep hashing `catalog.json`, and proves the two differ. All 52 tests pass.

Fresh Haiku and DeepSeek reader smokes passed 6/6 with M-catalog hash `ede57e6faa05` on repaired harness hash `a7a765540911`. All six Fable, Kimi, and GPT adapter paths passed on that harness hash.

Copilot's next pass found that the ledger schema could still make legacy and current smokes sound simultaneous. D-031 and `ledger/README.md` now state the exact shapes: four legacy `tier: smoke` rows, one harness-written `tier: qualification` row per completed reader-profile batch, and no new smoke rows. Gates may use `passed` only to control measured execution; consumers exclude every `E-09-cold-reader` row from outcome aggregates. A fresh Claude Haiku 4.5 process correctly restated all consumer and writer obligations without project settings, tools, or session context.

After superseded smokes were removed, Copilot found session-specific temporary project identifiers inside two retained legacy Warp notification strings. The sanitizer now redacts `e09-tool-*`, `e09-text-*`, and `e09-codex-*` identifiers as `<PROJECT_ID>`. Its regression exercises the embedded-string form, and the committed-artifact scan applies the production sanitizer to every retained smoke JSON file. The two legacy records were repaired. All 52 tests pass. Fresh Haiku and DeepSeek reader smokes passed 6/6 on harness hash `ba1f90856583`, and all six Fable, Kimi, and GPT adapter paths passed on that hash. The previous current smoke namespaces were removed; only the new current namespaces and the four ledger-linked legacy namespaces remain.

Copilot's next pass found that D-031 and `ledger/README.md` allowed a gate to read `passed` from any E-09 cold-reader row, including the four legacy smokes. The binding text now defines cold-reader rows as precondition records, makes the legacy rows unreadable by gates, defines the exact current qualification key, blocks on a missing or failed qualification, and excludes every cold-reader row from outcome aggregates. Fresh Haiku cold reads exposed and drove repairs to the tier identity, key selection, and missing-row behavior. The final no-context read correctly restated every writer, gate, and consumer obligation and found no material contradiction or ambiguity.

## D-032 raw-artifact storage review

The user chose one deterministic raw archive on an immutable GitHub Release plus one committed manifest. An external mirror is not required in v1. GitHub immutable releases were enabled for `mlamp/meta-skills` before implementation. This policy is prospective; no measured E-09 call ran during the change.

Fresh Haiku 4.5 processes with no session context cold-read each binding-text repair. The first reads exposed ambiguous inventory counts, sanitizer failures, smoke retention, `supersedes`, operator acceptance, publication order, remote-check ownership, immutable-setting enforcement, and local-retention wording. The final full-policy read used the provider's structured-output tool with a deliberately simple string schema. It correctly restated the seven stages, separate `publish-release` and `finalize` checks, API-enforced immutable setting, manual-only local deletion, legacy boundary, and no-mirror risk, with `ambiguities: NONE`. A final field-only read correctly separated pre-publication raw-root and schedule pins from post-publication release and archive attestation subjects, also with no ambiguity. One earlier attempt exhausted structured-output retries on a more complex array schema; it was a formatting failure and did not count as a comprehension result.

Fable 5 high and Kimi K3 high independently reviewed the complete implementation and simulated interruption paths. Their material findings were repaired:

- Draft and published releases are resolved through an authenticated, paginated release listing. Lookup errors fail closed. The published tag endpoint is used only after publication.
- A partial draft re-uploads the exact assets. A retry after publication waits for immutability, repeats fresh-download verification, and writes or accepts the identical tracked manifest copy.
- The released manifest is compared with the local or tracked manifest, never with itself.
- Finalization binds the manifest to the current repository, batch, freeze, commit, provenance, and release names. It also rechecks every local raw byte against the published inventory before computing metrics.
- Sanitization scans the same no-follow regular-file bytes that enter the archive. Pack-time patterns cover credential values, bearer and assignment forms, POSIX and Windows host paths, UUIDs, and temporary project ids.
- Transfers have explicit long timeouts. Artifact packing is idempotent for an unchanged local pair. The command prints the batch id and release tag.
- CI accumulates every committed-manifest failure explicitly and uses read-only repository and attestation permissions.

Kimi suggested replacing the local path passed to `gh release verify-asset` with an asset name. That suggestion was rejected: the installed CLI and official manual define the argument as `<file-path>`, and verification intentionally checks the freshly downloaded local archive. The exclusive freeze writer also remains unchanged; it prevents an executed freeze from being silently overwritten. This design change commits a new `freeze.json` only after final code and review bytes are fixed.

The final repair reviews converged on one remaining issue: local adjudication or metadata could change after publication and alter computed metrics. Finalization now rebuilds the frozen plan and runs the same source-to-manifest byte check before remote verification or arithmetic.

Copilot's first PR review found ten inline blockers and twelve suppressed hardening notes. All were treated as review input. The repaired boundary now uses a trusted base-branch verifier on a separate runner from credential-free candidate tests; binds remote evidence to the current repository; cross-checks ledger, manifest, attestation, and result pins; requires the pack-generated plan and raw root at both release commands; rejects root links and traversal errors; scans every nonempty configured credential and decoded JSON string; validates manifest counts and normalized timestamps; uses fail-closed release listing and atomic retryable writes; rechecks supersession at publication; binds raw records to their paths; recomputes schedules; validates the exact retry and exclusion protocol; and requires local `HEAD` to equal the commit that last changed `freeze.json` through publication and finalization.

Fresh no-context Haiku reads then tested the revised binding text. The first exposed that the prose did not say whether checks exit nonzero, define the exact source rebind, require exhaustive inspection, or distinguish transient retry from a content failure. Those rules were made explicit. A later read found no ambiguity but invented an operator identity absent from the text, so it did not count. The final read added no facts, correctly restated the exact commit and new-namespace rule, all seven stages, automated gates, exhaustive inspection, PR credential isolation, repository and ledger checks, transient retry, and new-batch behavior, with `ambiguities: NONE`.

Fable 5 xhigh and Kimi K3 high then reviewed the Copilot repair diff. Both found the same material ledger bypass: a self-consistent receipt could point outside the remotely verified manifest set, omit evidence on a new measured row, or misattribute another experiment. Fable also found that candidate code still ran in a `pull_request_target` job. The workflow now runs candidate code only on ordinary `pull_request`, while the target event runs only trusted base code against the event's pinned merge commit. Ledger verification requires evidence on every exact numeric experiment row except the four named E-07/E-08 legacy ids; binds experiment, batch, standard paths, manifest, result row, and attestation subjects; and performs its own cached fresh-download verification so the actual release id and receipt must match. The manifest format moved to schema 2 before any manifest existed. Nested JSON sanitizer decoding, finite elapsed-time checks, explicit shell failure behavior, raw-mutation coverage, duplicate-release lookup, and asset-name tests were also added.

Reviewer suggestions were not copied blindly. `finalize` does not unpack `artifact_paths` and already repeats `verify_source`; that concern was false. The two-attempt allowlist is the exact `call_record` protocol. A nonempty one-character credential remains blocking because exact configured values are the approved gate. The commit that last changed `freeze.json` remains reachable and checkable under squash or merge commits; the workflow does not require the merge commit itself to be the frozen commit.

Fable and Kimi then re-read the focused repairs. Both confirmed that the original ledger and event-boundary blockers were closed. Fable found two remaining fail-open edges: an absent or stale merge SHA and a `find` failure hidden by process substitution. The workflow now validates the event SHA, checks the candidate commit and its second parent against the event, and materializes the manifest list before the verification loop. Kimi found that deleting evidence or rewriting an artifactless legacy row could otherwise make the verification set vacuous. CI now requires the candidate ledger to be a byte-for-byte append-only extension of the trusted base ledger, and the verifier requires all four named legacy rows with their complete canonical hashes. Main-branch verification compares with the previous main ledger.

The next Haiku cold read correctly restated the repaired trust boundary but mistook the merge-SHA check for the required post-merge lifecycle proof. The binding text then defined that proof as a synthetic one-record publication run from the merged exact frozen commit. It names the non-evidence experiment and tag, forbids result and ledger rows, defines the issue record, and keeps measured calls blocked until fresh download and both attestations pass. A fresh full-policy read separated that proof from CI. A field-only read correctly restated its timing, commit, scale, experiment, tag, non-evidence status, issue record, close gate, and local retention.

Fable's final xhigh pass confirmed all earlier blockers closed, then found two new contradictions. Main-push CI read the push payload's `before` value as an unmapped shell variable, so it would stop before verification. The workflow now maps that field explicitly and its static test pins the mapping. The lifecycle smoke also said to run all seven stages while forbidding the result and ledger writes that define stage seven. The smoke now ends after remote verification at stage six; the measured E-09 finalizer remains stage seven and cannot run on synthetic smoke data.

A fresh no-context Haiku read correctly restated the corrected smoke timing, six-stage scope, measured-only finalizer, commit, scale, experiment, tag, non-evidence status, issue record, close gate, and local retention, with no ambiguity. Kimi K3 high then confirmed both Fable repairs and found no further trust-boundary, ledger, or retry issue. Its only blocker was the expected freeze drift from those just-edited workflow, test, and review bytes. The freeze was regenerated after this note.

Copilot's second PR pass found eight inline and seven suppressed edge cases. The repairs bind the complete sanitizer policy, reject cross-platform unsafe paths, decode nested JSON strings until exhausted with fail-closed limits, require explicit `supersedes`, reproduce archives byte for byte, bind working source bytes to the frozen commit, require remote default-branch containment, preflight conflicting tags and tracked copies, validate E-09 metadata and successful payloads, reject redirected namespaces before reads, and recompute an existing compact result before ledger repair. The suppressed findings received the same treatment as inline comments.

Fable 5 xhigh found that the first sanitizer-policy hash was circular: a coordinated plan and manifest edit could weaken it. The final verifier instead reads the canonical freeze index and sanitizer source from the frozen Git object, derives the complete provenance set and policy, and rejects numeric experiments that redirect either source. It also corrected prose that had put a GitHub tag lookup before GitHub contact. Kimi K3 high separately found that pack and finalization relied on the measured gate for clean frozen bytes while the new verifier was explicit only in release commands. Both commands now invoke it directly.

Fable's closure review confirmed both code blockers closed, then found that deleting the new pack or finalize calls would not fail a test. Call-site regressions now stop before remote verification, and negative tests pin interview derived-field and substitute-blind validation. Kimi's independent closure found no circularity, ordering inversion, or false-evidence path and returned `CLEAN`. Its input preceded those final test additions, so its minor call-site coverage note was resolved by the same Fable repair. Optional date, memory, Windows-device-name, and diagnostic-error hardening did not expose false evidence and was not added. No artifact-backed schema-2 manifest exists, so adding required fields before the first manifest does not create a compatibility exception.

A no-context Haiku read of the repaired policy confused archive-only `verify-local` with the frozen working-source check and omitted `artifact-pack` and `stage-release`. The binding text now names the four source-checking commands and says that `verify-local` does not replace them. A fresh field-only read correctly named all four commands, separated archive verification, identified the frozen provenance and sanitizer sources, separated the two publication preflights, preserved the six-stage smoke record, and reported no ambiguity.

Copilot's third PR pass found four inline and four suppressed integrity gaps. The repaired release path now derives the E-09 plan from the frozen harness instead of trusting the saved plan. Adjudication files are derived from current disagreements, record-manifest paths stay inside the measured namespace, and failed or excluded records cannot carry a result. Finalization rechecks every source byte after remote verification and before persistence. Ledger verification binds the freeze and the complete compact-result row set. CI downloads ledger-backed releases once and verifies only true orphan manifests separately.

Fable 5 xhigh found that the first orphan skip used an untrusted filename as a `grep` pattern. Replacing `grep` with exact string comparison closed that direction, but its closure review exposed the matching line-delimited producer as the same ambiguity in reverse. The final handshake uses NUL-delimited bytes, a fail-closed parser in the trusted verifier, and exact filesystem-byte membership. Its last focused review returned `CLEAN`. Kimi K3 high found no false-evidence blocker in the complete repair. Its endorsement of the old `grep` seam was rejected because Fable supplied a concrete bypass. Its useful test-pressure notes produced direct stale-pending, missing-pair, duplicate-resolution, child-symlink, and hard-link regressions. Suggestions already enforced by full manifest validation, the existing freeze field, and the packager's hard-link gate were not duplicated.

No-context Haiku reads exposed shorthand around adjudication filenames, source scope, independent release-command checks, freeze identity, and compact-result membership. The binding text now names the exact files, bytes, commands, schema, and `results_path` relation. The final read restated all five obligation groups without adding facts and reported `CONTRADICTIONS: NONE`.

The artifact suite has 40 tests, the E-09 harness suite has 77, and the agent-voice artifact suite has 24. Reviewer advice, cold reads, and these tests are context, not effectiveness evidence. The actual immutable-release lifecycle proof must use the merged frozen commit before measured E-09 trials.

Copilot's fourth PR pass found four inline and three suppressed trust-boundary gaps. CI enumerated only regular orphan manifests; artifactless cold-reader rows and artifact-backed E-09 metrics were under-validated; duplicate JSON keys and non-finite extensions could alter sanitized meaning; JSON booleans passed one numeric identity check; and measured namespaces were not validated before the first provider call. The repair enumerates every manifest path type and fails non-regular paths before network use. It uses strict JSON for documents, JSONL, provider envelopes, and recursively decoded JSON strings, including overflowed exponents. Repository booleans fail. Every measured phase creates and validates its namespace before calls.

Trusted ledger verification now pins the four historical cold-reader smokes, validates new qualification rows against the complete current key, and preserves append-only historical qualifications when any keyed input changes. The local measured gate inventories and regrades every current qualification case record, retry record, start marker, summary, and derived ledger row. It requires the current rows to remain uncommitted additions even when the rest of the tree is clean. Completed failed qualifications still regrade and repair an interrupted ledger append. These records are a local integrity gate, not provider-signed proof against a hostile local writer.

Post-D-032 numeric results require a registered trusted validator. The E-09 validator checks the complete typed row, exact manifest identity, ordered five-run arms, internal rates and statistics, exactly one row per frozen model family, and a content address that includes the canonical completion timestamp. It rederives summaries, pooled and paired values, rendered selected-relevant density, counts, judge agreement, and C19–C22 from the run records. Over-cap or contract-violating interviews make the claim screens incomplete. A cross-module test feeds harness-written qualification and result identities through the trusted verifier. That test exposed and corrected a 320-versus-340 assertion-count error before any qualification run.

Fable 5 xhigh and Kimi K3 high reviewed the repairs independently. Fable found the future-history failure, duplicate-family path, timestamp exclusion, missing parity test, clean-tree committed-only bypass, failed-qualification repair regression, partial-key history check, and strict-provider-output error leak. Kimi independently found the history, parity, overflow, qualification, and duplicate-family issues, then found that contract density lacked the rendered-relevant primitive needed for trusted rederivation. Each concrete counterexample was repaired and regression-covered. Suggestions that local files could prove provider calls were rejected as an impossible attestation claim and the boundary was documented honestly. Fable's focused closure returned `CLEAN` on the four late gate/parser/history repairs; its final density check requested one further intersection with selected relevant rules, which is now the production helper and has a direct regression.

The artifact suite now has 48 tests, the E-09 harness suite has 85, and the agent-voice artifact suite has 24. Reviewer advice and these tests remain context, not effectiveness evidence. No measured E-09 provider call ran in this PR.

Kimi's closure found one remaining free input to C20: contract density could not be rederived because the row omitted the number of selected relevant rules actually rendered. The run row now carries `rendered_relevant`; production intersects rendered, relevant, and selected IDs, and trusted code derives density from that count and contract tokens. Claim completeness now also requires zero over-cap and contract-violating interviews. Fable's final focused check returned `CLEAN`, and a direct regression excludes relevant-but-unselected rules from the numerator.

A fresh Claude Haiku 4.5 process with no project settings, tools, or session context read only the final binding-text diff. It correctly separated new and historical qualifications, local integrity from provider attestation, uncommitted gate rows, namespace safety, strict JSON, all manifest path types, registered numeric schemas, exact E-09 family multiplicity, derived metrics, timestamp identity, and claim completeness. It reported `CONTRADICTIONS: NONE`.

Copilot's fifth PR pass found three inline and four suppressed trust-boundary gaps. The repair rejects the dot path as an empty relative member. Qualification evidence must resolve to its lexical repository path before any record read. The latest adapter-smoke attempt is accepted only after exact inventory, identity, retry, schema, semantic, count, key, and summary revalidation. Every measured phase validates existing metadata before a record can be reused or a provider can be called. The measured id hashes the complete validated freeze object, including its UTC creation date. Successful raw records retain provider identity metadata that the packager checks against frozen profiles. Measured start and completion run ids are rederived from the current namespace and exact event payload.

Fable 5 xhigh and Kimi K3 high independently reviewed those repairs. Kimi found no bypass in the original seven boundaries. Fable found two further closed-world identity gaps: Codex could claim an impossible reported model, and provider lists could contain unapproved extras. The validator now requires both lists to be subsets of frozen allowlists, requires every pinned primary identity, and pins `firstParty` for Haiku, Fable, and Kimi. The same rule runs at call time and during persisted-evidence validation. Kimi also noted that Python considers `6.0 == 6` and `True == 1`. It did not find an evidence bypass, but exact JSON identities, schedules, summaries, qualification grading, and freeze schema versions now compare through canonical strict JSON so the stored type cannot drift. Fable's final focused closure returned `CLEAN`.

The artifact suite has 48 tests, the E-09 harness suite has 91, and the agent-voice artifact suite has 24. No measured E-09 provider call ran.

A fresh Claude Haiku 4.5 process with no project settings, tools, or session context read only the final binding-text diff. It correctly restated the complete freeze identity, lexical qualification namespace, exact adapter-smoke revalidation, phase-entry metadata, persisted provider identity, and namespace-derived call-manifest identities. It reported `CONTRADICTIONS: NONE`.

Copilot's sixth PR pass found two inline and seven suppressed gaps. Eight were valid. DeepInfra response syntax failures no longer enter the transport retry. Measured retries recover both append crash windows without repeating a durably started provider call. Qualification and smoke summaries are read only after namespace and inventory validation. A partial qualification namespace blocks calls. The configured DeepInfra provider and the frozen Codex minimum version are revalidated. Remote verification fetches the provenance index, every named source, and the sanitizer policy from the frozen commit and binds their bytes to the manifest. Copilot's claim that the trusted CI path already executed candidate code through `verify_trusted_plan` was false: that function is called only by the local stage and publish commands. The checker now refuses every external executable root unconditionally, so ambient `gh` credentials cannot make a future caller unsafe.

Fable 5 xhigh found that the first external-root refusal depended on token environment variables and therefore missed `gh auth` keyring credentials. The refusal is now unconditional, the harness path and working directory come only from the running packager root, and Fable's focused closure returned `CLEAN`. A local review then found two related first-run edges. Qualification now creates and validates its exact namespace before the first provider call, including when an absent leaf sits beneath a redirected parent. GitHub Contents API can resolve an in-repository symlink and report the target as a file; remote source reads now recompute the returned bytes' Git blob identity and reject that case. A live check accepted a regular E-09 source on `main` and rejected the repository's linked `AGENTS.md`.

Kimi K3 high independently reviewed the final focused code and tests with no tools or project context and returned `CLEAN`. It confirmed the no-repeat measured restart states, namespace-before-read ordering, resolved-symlink rejection, provider and version gates, external-root refusal, and remote verification order. A fresh no-context Haiku read first omitted the first-run redirected-parent obligation. The binding sentence was corrected to include qualification, and the final read correctly restated absent, partial, linked, and redirected namespaces; both restart states; smoke ordering; provider and CLI identities; remote source and symlink checks; and the external-root prohibition. It reported `CONTRADICTIONS: NONE`.

The artifact suite has 52 tests, the E-09 harness suite has 97, and the agent-voice artifact suite has 24. Reviewer advice, cold reads, and these tests are context, not effectiveness evidence. No measured E-09 provider call ran.
