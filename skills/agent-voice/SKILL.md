---
name: agent-voice
description: Generates a per-project communication contract for Claude Code — a custom output style plus deterministic settings — after checking the project's existing instruction stack for contradictions. Use when asked to create or tune an output style, an append-system-prompt, or a communication style, to cut verbosity, banned phrases, or model tics, to stop co-author trailers, or to set how an agent talks in a project. Keywords, output style, outputStyle, append-system-prompt, system prompt, communication contract, verbosity, banned phrases, tics, attribution, agent voice.
status: draft
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# agent-voice

The problem: frontier coding models spend a large share of their output on prose nobody asked for — tic phrases, recap bloat, flattery, widened scope, mid-task check-ins. That costs output tokens and reader time; whether it comes from the model's training or the harness is not established, and doesn't need to be. The lever this skill tests: a hand-written communication contract at the most persistent layer available (theory: docs/communication-contracts.md in the meta-skills repo).

The skill writes that contract for a target project and installs it as a Claude Code custom output style, routing to settings what settings control. Claude Code first; other CLIs get a derived append file on request. The contract is a hypothesis under test, not a proven fix — no claim behind it is validated (C13–C18; E-07's first single-turn measurements support tic and token suppression but not a system-prompt-placement advantage over CLAUDE.md). Say so in the hand-off.

## Inputs

- A target project path; default the working directory.
- The user's answers to the interview in step 2.

## Steps

Do all seven, in order.

1. Inventory. Read the target's CLAUDE.md files (project and user level), `.claude/rules/`, `.claude/settings.json` and `settings.local.json`, and any files in `.claude/output-styles/`. The inventory exists to catch contradictions and to find requirements a setting already handles — not to thin the contract. Name what you did not check (hooks, plugins, enterprise policy) as unchecked in the hand-off.
2. Interview, one short round:
   - Which tics or phrases does the user actually see? Seed the list with any found in the inventory.
   - Verbosity target and anything else they want the agent's voice to do.
   - Opt-ins: reference points (short codes like D1/R3 for findings, decisions, risks), aliases (micro-commands like `scr`), drive rules (a framed multi-step task runs to completion; no "should I continue?" check-ins).
   - Activation scope: personal `.claude/settings.local.json` (default) or shared `.claude/settings.json`. Shared changes every contributor's sessions — say so before they pick it.
   The default contract is: purpose, positive and negative patterns, boundaries, and one or two do/don't example pairs.
3. Route. Anything a setting controls deterministically goes to settings, never into the contract. Known case: co-author trailers and PR footers → `"attribution": {"commit": "", "pr": ""}`. This skill never adds hooks.
4. Draft one coherent contract from `references/contract-template.md`, adapted to the interview. Example pairs come from this project: a real task, a preferred (edited) response as "do", an observed verbose one as "don't". On a contradiction with the existing stack, stop and ask the user which rule wins — never layer a caveat on top of a conflicting rule. Skip only verbatim duplicates; a paraphrase existing elsewhere is not a reason to drop a rule.
5. Show, then write. Present every file as a diff and get a yes before writing:
   - `.claude/output-styles/<name>.md` — frontmatter `description` plus `keep-coding-instructions: true`, always. Without it a custom style replaces Claude Code's built-in software-engineering instructions.
   - The `outputStyle` key in the settings file chosen in step 2.
   - Only if asked: the portable append file, derived by stripping the style file's frontmatter. It is generated output — never edit it; regenerate it from the style file.
6. Cold-reader probe. Give a cheap headless model, with no session context, the generated contract alone and ask it to restate its obligations. Fix misreads in the contract and re-probe. Restatement measures comprehension, not compliance — say so.
7. Record. Write the run report (format: `python3 ${CLAUDE_SKILL_DIR}/scripts/finalize.py --help`) to a scratch file and run `python3 ${CLAUDE_SKILL_DIR}/scripts/finalize.py <report> <target>`. It appends to `ledger/runs.jsonl` when the working directory has one, else prints the line for the user to file.

## Known limits

- The style takes effect on the next session or after `/clear`, not immediately.
- Whether subagents inherit the output style is unverified — check before relying on it.
- Effectiveness rests on first measurements only (E-07, single-turn). The contract can pass its probe and still not change behavior in settings not yet measured.

## Rules

- A setting beats prose: never generate a prompt line for behavior a setting controls.
- One canonical contract file — the output style. Every other copy is derived, never edited.
- Never write outside the target's `.claude/` directory and its settings files.
- Never overwrite an existing output style, settings key, or contract without showing the diff and getting a yes.
- Never hand-write the ledger line; finalize.py is the only writer.
