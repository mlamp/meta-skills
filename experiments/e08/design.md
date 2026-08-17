# E-08 design — long-session placement A/B

Frozen before the runs. The E-07 follow-up its queued-work entry names: E-07 found the CLAUDE.md arm matching or beating the system-prompt arm in single-turn sessions; this tests the placement question where the system-prompt layer's persistence argument actually applies. Moves: C17 (and adds long-session evidence to C13).

## Question

When the probe arrives ~10k tokens into a session, does the contract at the system-prompt layer hold up better than the same text in CLAUDE.md?

## Sessions

Each rep is one 5-turn headless session (`claude -p`, then `--resume <session_id>` in the same working directory):

- Turns 1–4: filler — ~8.4k words of frozen text (materials.json: the public-repo transcript in thirds plus the three research notes) pasted as input, each demanding the one-word reply "noted". Context grows by input, not output, so growth is identical across arms and the E-07 confound (contract arms shortening their own context) cannot occur.
- Turn 5: the probe — E-07's T2 (redis recommendation), verbatim, judged by the same haiku gate.

## Arms

- `stock` — no additions (opus only; reference).
- `sysprompt` — `--append-system-prompt-file contract.md` passed on every call of the session.
- `claudemd` — contract.md as `CLAUDE.md` in the session's working directory, present from turn 1.

contract.md is byte-identical to E-07's (sha-pinned in the ledger line): same banned list, so C13/C17 numbers compare directly to E-07's single-turn T2 row.

## Families and size

- opus: 3 arms × 5 reps = 15 sessions (75 calls).
- kimi-k3 anchor: the two contract arms only × 5 reps = 10 sessions (50 calls). Resumes pin the wrapper slot (CLAUDE_KIMI_SLOT), since a session exists only in the slot that created it.

## Metrics

On the probe turn only: banned-phrase hits, em-dash count, output tokens, chars, haiku judge. Filler-turn output tokens and the probe turn's input/cache token counts are recorded as evidence of comparable context size. One `type: "experiment"` ledger line per family (D-023).

## Known limits

- One probe task (T2) — chosen for direct comparability with E-07's strongest row; generality across tasks is not claimed.
- ~10k tokens is a modest session; this bounds "long" from below, not from above. If placement still doesn't separate here, the next escalation is a much longer or compacted session.
- The stock arm exists only in opus, to bound the contract effect at depth; the placement question needs only the two contract arms.
