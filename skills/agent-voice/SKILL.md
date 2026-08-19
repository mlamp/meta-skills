---
name: agent-voice
description: Generates and installs a two-layer Claude Code communication contract—a user-level voice core plus a project-specific delta—and routes deterministic behavior to settings. It inventories and migrates existing voice rules without duplication, and can instead create a private custom output style or a derived append-system-prompt file. Use when asked to create or tune an output style, append-system-prompt, communication style, verbosity, banned phrases, model tics, co-author trailers, or how an agent talks in a project. Keywords, output style, outputStyle, append-system-prompt, system prompt, communication contract, verbosity, banned phrases, tics, attribution, agent voice.
status: draft
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# agent-voice

Frontier coding models spend output on prose the reader did not ask for: tic phrases, recap bloat, flattery, widened scope, and mid-task check-ins. This skill turns the user's preferences into persistent instructions without duplicating the existing stack.

The default delivery is a user-level core plus a project delta in Claude rules files. Settings own behavior they can control. In E-07, listed phrase hits fell from 7 to 0 for Opus and 2 to 0 for Kimi; contract arms used roughly 36–68% fewer output tokens at equal coarse judge pass. E-08 found a roughly 48% reduction at about 37k context tokens. These results cover the tested task families and CLAUDE.md/system-prompt placements, not `.claude/rules/` itself. C14–C16 and C18 remain unmeasured.

## Inputs

- A target project path; default to the working directory.
- The user's answers to the interview in step 2.

## Steps

Do all seven in order. Track them in a seven-item task plan. Do not mark a step complete before its named outputs and gates are done.

1. **Inventory.** Read project `CLAUDE.md`, `AGENTS.md`, `.claude/rules/**/*.md`, `.claude/settings.json`, `.claude/settings.local.json`, and `.claude/output-styles/*.md`. Read user `~/.claude/CLAUDE.md`, `~/.claude/rules/**/*.md`, `~/.claude/settings.json`, and `~/.claude/output-styles/*.md`. Resolve symlinks before treating files as separate owners. Classify each instruction as voice-shaped or project-factual. Map one current owner for every voice rule. Mark equivalent wording as a migration candidate, not a reason to create a second copy. List hooks, plugins, managed policy, and anything else not inspected as unchecked.
2. **Interview in one short round.** Ask which observed tics to ban, the verbosity target, and what else the voice should do. Show the default-on user-core baseline from `references/contract-template.md`; ask what to remove. Offer reference-point codes, exact-message aliases, and drive rules as opt-ins. Choose delivery:
   - Default: `~/.claude/rules/<name>.md` for personal rules plus `.claude/rules/<name>.md` for project-only rules. The project delta is committed and affects teammates; say so before approval. Do not write an empty delta.
   - Single rules layer on request, at the ownership scope the user selects.
   - Custom output style on request: default to a private, project-named `~/.claude/output-styles/<project>-<name>.md`, activated in target `.claude/settings.local.json`. Merge core and delta only when those rules are not already loaded elsewhere. A team-shared `.claude/output-styles/` style requires explicit approval after warning that its rules and project setting affect contributors.
   - Portable append file only on request. It is derived from the selected canonical source files in owner order; never edit it directly.
3. **Route.** Put behavior a setting controls into settings, never prose. Route personal behavior to `~/.claude/settings.json`, team-agreed behavior to committed `.claude/settings.json`, and a private project choice to `.claude/settings.local.json`. Known case: co-author trailers and PR footers use `"attribution": {"commit": "", "pr": ""}`. Never add hooks.
4. **Draft and prepare migrations.** Build the core and delta from `references/contract-template.md`. A rule true across the user's projects belongs in the core. A rule wrong or meaningless elsewhere belongs in the delta. Project examples always belong in the delta. Prepare, but do not apply, a removal diff for every equivalent voice rule in an inspected user or project instruction file; project-factual text never moves. Stop on a real contradiction and ask which rule wins. A verbatim duplicate is still a migration candidate.
5. **Decide from diffs.** Show every proposed file and migration as a diff in one approval pass, with a separate decision for each migration. Write nothing yet. If the user approves a migration, move the rule to its contract owner. If they decline, the existing file remains the sole owner and the equivalent rule is omitted from the contract. State when that leaves a project-local rule unavailable in other projects. Rebuild the ownership map after the decisions; every voice rule must have one owner.
6. **Preflight.** Materialize the approved artifacts in an OS temporary directory. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/validate_artifacts.py --help`, then validate every proposed rules file, output style, settings file, derived append file, and retained existing owner. The validator checks exact duplicates only; inspect paraphrases yourself. Give a cheap headless model, with no session context, the artifacts that will actually be loaded—core and delta, a single rules file, an output style, or an append file—plus retained existing voice rules. Label each by source. Ask it to restate obligations and precedence. Restatement measures comprehension, not compliance. Fix a material misread, re-run validation and the probe, then return to step 5 for approval of the changed diff.
7. **Write, verify, record, and hand off.** Write the exact approved bytes. Re-run the same validator against the installed files. On failure, do not repair silently; return to step 5 with a corrective diff. Read the report schema with `python3 ${CLAUDE_SKILL_DIR}/scripts/finalize.py --help`. Author the generation report in an OS temporary file, then run `finalize.py <report> <target>`. The finalizer reads the report and records the ledger line; it does not author the report or transform any artifact. In the closing response, list files written and migrated, declined migrations and consequences, activation scope, settings routed, validation and probe results, unchecked surfaces, next-session activation timing, evidence limits, and the finalizer result.

## Known limits

- Changes take effect after `/clear` or in the next session.
- E-07/E-08 tested CLAUDE.md, not `.claude/rules/`. Contexts beyond about 37k tokens and post-compaction behavior are unmeasured.
- Whether subagents inherit the contract is unverified; check before relying on it.
- User-level rules reach only harnesses that load Claude's user configuration. Repo-only CLIs and wrappers with another config directory may skip them.
- A clean restatement probe does not prove runtime compliance.

## Rules

- A setting beats prose.
- Every voice rule has one owner in the effective stack. The installed core and delta are canonical peers; retained existing rules remain their own owners. Every append file is derived.
- Write only approved artifacts at `~/.claude/rules/`, `~/.claude/output-styles/`, target `.claude/rules/`, target `.claude/output-styles/`, selected user or target settings files, approved migrations in inspected user or project instruction files, the requested append path, OS temporary artifacts and report, and the repository ledger through `finalize.py`.
- Never overwrite an existing rule, style, setting value, or instruction without its diff and approval.
- Never hand-write a ledger line.
