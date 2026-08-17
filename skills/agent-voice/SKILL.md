---
name: agent-voice
description: Generates a per-project communication contract for Claude Code — a custom output style plus deterministic settings — after checking the project's existing instruction stack for contradictions. Use when asked to create or tune an output style, an append-system-prompt, or a communication style, to cut verbosity, banned phrases, or model tics, to stop co-author trailers, or to set how an agent talks in a project. Keywords, output style, outputStyle, append-system-prompt, system prompt, communication contract, verbosity, banned phrases, tics, attribution, agent voice.
status: draft
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# agent-voice

The problem: frontier coding models spend a large share of their output on prose nobody asked for — tic phrases, recap bloat, flattery, widened scope, mid-task check-ins. That costs output tokens and reader time; whether it comes from the model's training or the harness is not established, and doesn't need to be. The lever this skill tests: a hand-written communication contract at the most persistent layer available (theory: docs/communication-contracts.md in the meta-skills repo).

The skill writes that contract in two layers — a user-level core (the person's voice, all their projects) and a per-project delta holding only what the core doesn't say — installed as always-loaded rules files, routing to settings what settings control. It also migrates voice-shaped rules out of the project's existing instruction files, with approval, so the contract replaces duplication instead of adding to it. Claude Code first; other CLIs get a derived append file on request. Measured so far (E-07, E-08): the contract cuts tics to zero and output tokens by roughly 40–60% at equal task success, in two model families, single-turn and ~37k tokens deep — but placement made no difference (system prompt vs context file, C17 refuted), which is why the default delivery is the simpler layer. C14–C16 and C18 remain unmeasured. Say where the evidence stops in the hand-off.

## Inputs

- A target project path; default the working directory.
- The user's answers to the interview in step 2.

## Steps

Do all seven, in order.

1. Inventory. Read the target's CLAUDE.md/AGENTS.md files (project and user level), `.claude/rules/` (both levels), `.claude/settings.json` and `settings.local.json`, and any files in `.claude/output-styles/`. Classify every instruction found: voice-shaped (how the agent talks and works — tone, verbosity, response shape, scope discipline, check-in behavior) or project-factual (build commands, architecture, domain rules, artifact conventions). Voice-shaped text in project files is a migration candidate for step 4; the classification is shown to the user, never applied silently. The inventory also catches contradictions and requirements a setting already handles — it never thins the contract. Name what you did not check (hooks, plugins, enterprise policy) as unchecked in the hand-off.
2. Interview, one short round:
   - Which tics or phrases does the user actually see? Seed the list with any found in the inventory.
   - Verbosity target and anything else they want the agent's voice to do.
   - Opt-ins: reference points (short codes like D1/R3 for findings, decisions, risks), aliases (micro-commands like `scr`), drive rules (a framed multi-step task runs to completion; no "should I continue?" check-ins).
   - Delivery scope. Default is two layers: a user-level core at `~/.claude/rules/<name>.md` (personal voice — banned phrases, response shape, generic boundaries, drive; never imposed on teammates) plus a project delta at `.claude/rules/<name>.md` holding only what the core doesn't say — example pairs, migrated rules, team-agreed norms, project terminology. The project file is committed and applies to every contributor — say so before they accept it. Single layer, or a custom output style, on request. The split test for any line: would it be wrong or meaningless in the user's other repos? Yes → project; no → core.
   The default contract is: purpose, positive and negative patterns, boundaries, and one or two do/don't example pairs.
3. Route. Anything a setting controls deterministically goes to settings, never into the contract. Known case: co-author trailers and PR footers → `"attribution": {"commit": "", "pr": ""}`. This skill never adds hooks.
4. Draft and migrate. Draft the contract layers from `references/contract-template.md`, adapted to the interview; the delta contains nothing the core (or the user's existing rules files) already says. Example pairs come from this project: a real task, a preferred (edited) response as "do", an observed verbose one as "don't". For each voice-shaped rule found in the project's instruction files, propose moving it into the contract — shown as a diff on both files, applied only with a yes; project-factual text never moves. On a contradiction with the existing stack, stop and ask the user which rule wins — never layer a caveat on top of a conflicting rule. Skip only verbatim duplicates; a paraphrase existing elsewhere is not a reason to drop a rule from whichever layer owns it.
5. Show, then write. Present every file as a diff and get a yes before writing:
   - Default: the user-level core at `~/.claude/rules/<name>.md` and the project delta at `.claude/rules/<name>.md` (either may be skipped per step 2; a delta with nothing to say is not written) — no frontmatter, no settings key. Migration edits to existing files land in the same approval pass.
   - Output-style delivery only when chosen: `.claude/output-styles/<name>.md` with frontmatter `description` plus `keep-coding-instructions: true`, always (without it a custom style replaces Claude Code's built-in software-engineering instructions), and the `outputStyle` key in settings.
   - Only if asked: the portable append file for other CLIs, derived from the canonical file (strip frontmatter if any). It is generated output — never edit it; regenerate it.
6. Cold-reader probe. Give a cheap headless model, with no session context, the generated contract alone and ask it to restate its obligations. Fix misreads in the contract and re-probe. Restatement measures comprehension, not compliance — say so.
7. Record. Write the run report (format: `python3 ${CLAUDE_SKILL_DIR}/scripts/finalize.py --help`) to a scratch file and run `python3 ${CLAUDE_SKILL_DIR}/scripts/finalize.py <report> <target>`. It appends to `ledger/runs.jsonl` when the working directory has one, else prints the line for the user to file.

## Known limits

- Delivery takes effect on the next session or after `/clear`, not immediately.
- The placement evidence (C17 refuted, E-07/E-08) tested CLAUDE.md itself; `.claude/rules/` is the same always-loaded layer but was not its own experiment arm. 100k+ and post-compaction sessions are unmeasured.
- Whether subagents inherit the contract is unverified — check before relying on it.
- User-level rules reach only harnesses that read the user's config: other CLIs reading the repo (AGENTS.md) never see them, and wrapper CLIs with their own config dir likely skip them too (unverified). Cross-harness projects need the project layer or the derived append file.
- Measured effects are E-07/E-08's task families only. The contract can pass its probe and still not change behavior in settings not yet measured.

## Rules

- A setting beats prose: never generate a prompt line for behavior a setting controls.
- One canonical contract file — the delivered rules file (or output style). Every other copy is derived, never edited.
- Never write outside the target's `.claude/` directory and its settings files.
- Never overwrite an existing output style, settings key, or contract without showing the diff and getting a yes.
- Never hand-write the ledger line; finalize.py is the only writer.
