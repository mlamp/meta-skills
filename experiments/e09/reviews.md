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
