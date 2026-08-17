# Fixing "smartass" Opus 5 with system prompt appends

- Source: github.com/disler/fixing-smartass-opus-5 (MIT) + video walkthrough (YouTube S_QdQ1G4GlU, IndyDevDan) · retrieved 2026-08-18
- Raw transcript: research/sources/disler-fixing-smartass-opus-5-transcript.txt
- One line: a hand-written communication contract appended to Claude Code's system prompt (`--append-system-prompt-file`) to cut a verbose model's tics, output tokens, and scope creep; five reusable sections; evidence is single side-by-side runs.

## The argument

Two prompt surfaces exist: the user prompt (one task) and the system prompt (every task). Every word in the system prompt multiplies over every exchange, so global behavior fixes belong there, not in per-task prompting or skills. Write the contract by hand — it is the highest-leverage document in the setup.

## The five sections of the shipped prompt

1. **Purpose** — a short peer-to-peer contract ("no-BS, clear, concise, actionable"), with a why. No role-play.
2. **Positive / negative patterns** — do-bullets (most important information last, state each fact once, match detail to task, challenge wrong assumptions, one paragraph over two) plus a banned-phrase list ("load-bearing", "worth stating plainly", "the real tension"), no flattery, no decorative headings, few em dashes.
3. **Reference points** — short codes per item class (D1 decisions, O1 options, F1 findings, R1 risks, Q1 questions, A1 actions) when presenting three or more; codes persist through the conversation; follow-ups become cheap ("talk more about R6").
4. **Hard operational boundaries** — deliver only what was requested; no widening into cleanup/refactoring/docs; no speculative abstractions; no completion claims without evidence; no co-author in commits; concise restatement of completed work.
5. **Aliases + examples** — inline micro-commands (`scr` simplify-compress-repeat, `eli`, `foc`, `ref`) that expand only when sent alone, and do/don't example pairs. "In-context distillation": paste a preferred model's (edited) response as a "to do" example.

## Method notes

- Iterated live against a control: two Claude Code panes, stock vs appended, same summarize-a-blog task, comparing tone, tics, and wall time / output tokens.
- All evidence is single runs; no repetition, no variance, no token counts recorded beyond screen reading.
- Acknowledged limits: banned phrases still slip through (non-determinism), prompt needs re-tuning per model release, aggressive compression can lose needed context.

## What we take, what we don't

- Take as claims to test (C13–C17): banned-phrase lists, reference points, aliases, example pairs, and the placement question (system prompt vs CLAUDE.md).
- Don't take: the "never add a co-author" prompt line — Claude Code's `attribution` settings object does this deterministically. A setting beats prose wherever one exists.
- Don't take: the effectiveness demos as evidence. Single runs are context (house rule; C10, C11).
