# Communication contracts — problem and theory

The framing behind the agent-voice skill (D-021, D-022). This is a design doc, not binding text; the claims it rests on are C13–C18 in research/CLAIMS.md, all unproven here.

## Problem

Frontier coding models spend a large share of their output on prose the reader did not ask for. Opus 5 is the current instance, but the pattern is general and recurs with each release:

1. **Tic prose** — recurring phrases, dash chains, decorative structure, flattery, recap bloat. Costs output tokens (money and latency) and reader time.
2. **Scope drift** — work widened into cleanup, refactors, and adjacent features nobody requested.
3. **Pause bias** — mid-task check-ins ("should I continue?") that stall multi-step work.
4. **Unevidenced claims** — "it works" without a command, output, and exit status.

Whether these come from the model's training, the harness system prompt, or both is not established here — that attribution is a hypothesis, and we don't need it to test the lever.

## Theory

Behavior wanted on **every** turn should be steered at the most persistent, highest-precedence layer available, because every word there multiplies over every exchange. The routing order:

1. **Deterministic setting** — when a setting controls the behavior, prose is the wrong tool (first case: git attribution).
2. **System-prompt layer** — a hand-written communication contract, installed as a Claude Code custom output style (persistent) or an append-system-prompt file (per-invocation, portable).
3. **Context files** (CLAUDE.md, rules) — for everything project-factual rather than voice-shaped.

A contract of patterns, boundaries, drive rules, and do/don't examples should make a frontier model more direct, cheaper, and steadier — and transfer across projects and model releases with retuning, not rewriting.

## Sources

All inputs are unproven here until measured (house rule):

- A public communication-contract repo and video — research/notes/disler-fixing-smartass-opus-5.md.
- Collected production practice from the user's own agent-instruction files — research/notes/collected-writing-for-humans.md (distilled; origin projects unnamed).
- Our own harness observations during meta-skills work.

## How we'd know

- **Supports the theory:** E-07 shows fewer tic hits and output tokens than stock at equal task success; C17 shows system-prompt placement beating CLAUDE.md placement for the same text.
- **Refutes it:** no measurable difference vs stock, or CLAUDE.md placement performing equally — then the output-style vehicle is redundant and the contract belongs in ordinary context files.

The skill that packages this for reuse: skills/agent-voice (status: draft until E-07 gives it evidence).

## First result (E-07, 2026-08-18)

The contract works; the layer claim is dead for the tested regimes. E-07: banned phrases to zero, em-dashes near zero, output tokens down 36–68% at equal task success, both families (C13 → testing). E-08: the effect holds with the probe ~37k tokens deep (−48%), and the two placements — system prompt vs CLAUDE.md — are indistinguishable within noise in both families. C17 → refuted for single-turn and ~37k-token sessions; the routing order above loses its layer-2-over-layer-3 preference for Claude Code unless 100k+ or post-compaction contexts reopen it. Practical consequence: what matters is that the contract exists and is loaded, not which of the two persistent layers carries it.
