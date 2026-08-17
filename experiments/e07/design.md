# E-07 design — contract A/B: banned-phrase suppression

Frozen before the arm runs. Moves C13 and C17 (research/CLAIMS.md).

## Question

Does a communication contract at the system-prompt layer reduce tic phrases and output tokens at equal task success — and does the same text in CLAUDE.md do worse?

## Arms

- `stock` — headless CLI, no additions. Baseline; runs first.
- `sysprompt` — `--append-system-prompt-file contract.md` (the system-prompt layer; stands in for the output-style vehicle, same layer).
- `claudemd` — the same contract text as `CLAUDE.md` in the run's working directory.

Each run executes in its own empty scratch directory so no project context leaks; only arm `claudemd` puts a file there.

## Families

- opus (`claude -p --model opus`) — the subject: the model whose verbosity motivated the effort. Full grid: 3 tasks × 3 arms × 5 reps = 45 runs.
- kimi-k3 (`claude-kimi -p`) — second-family anchor, task T2 only: 3 arms × 5 reps = 15 runs.

## Protocol

1. Baseline: run arm `stock`, all tasks, 5 reps per family cell.
2. Scan baseline responses against the candidate-tic list (harness `scan`). The banned list in the contract is frozen to phrases that actually appear in baseline (E-07 queue rule). If no phrase appears, C13's phrase test records a null; token and structure metrics still compare.
3. Write `contract.md` from the agent-voice default template: purpose, patterns (banned list from step 2), boundaries, one example pair. The example pair must not overlap any task (the investigation pair, not redis or summarize — both are tasks).
4. Run arms `sysprompt` and `claudemd`, same cells, 5 reps.
5. Judge: haiku answers yes/no per response — does it directly answer the task? Guards against terseness faking a win.
6. Finalize: the harness serializes one `type: "experiment"` ledger line per family (D-023). Raw responses stay in `raw/` as evidence.

## Metrics per response (final response text only)

Phrase regex hits (per phrase), em-dash count, semicolon count, bullet and heading counts, character length, `output_tokens` from the CLI's JSON, judge verdict.

## Known confounds (recorded, not fixed)

- The user-level `~/.claude/CLAUDE.md` and rules (including a conciseness rule) load in every opus arm. Constant across arms, so the comparison measures the contract's marginal effect on this user's real environment — the ecologically relevant question — not against a bare model.
- claude-kimi slots use their own config dir, so the kimi environment differs from the opus one; families are compared within themselves only.
- Judge is a single haiku pass — comprehension gate, not a quality score.
