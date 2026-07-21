---
name: review-skill
description: Reviews an agent skill — a skill directory or a single SKILL.md — against a two-layer rubric, scripted static checks plus six judged dimensions, and returns smell-tagged findings with evidence quotes and concrete fixes, 1–4 scores per dimension, and a ledger line. It never edits the reviewed files. Use when asked to review, critique, score, audit, or improve a skill, a SKILL.md, or a skill directory. Keywords, skill review, SKILL.md, skill smells, rubric, skill quality, trigger description, cold reader.
status: testing
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# review-skill

Reviews one skill and reports what's wrong, how bad, and how to fix it. Findings and scores only — this skill never edits the files it reviews. Not for measuring a skill's runtime effectiveness, and not for CLAUDE.md files or agent definitions.

Division of labor (D-015): you author the analysis — one markdown report. `scripts/finalize.py` owns the record: it verifies the report, extracts every evidence quote from the file spans you cite, runs the static checks, generates run IDs, timestamps, and SHAs, serializes, and commits the ledger line. You never write JSON, dates, or IDs.

## Inputs

- A path: a skill directory (preferred) or a lone SKILL.md. With a lone file, directory-dependent checks are reported as skipped — never guessed. No SKILL.md at the path — stop and say so; don't review arbitrary files.
- Optional: a cold-reader model, e.g. "cold-reader: haiku headless". Any headless CLI or model the user names.
- Eval-batch mode only: a batch id and sequence number from the harness.

## Steps

Do all six steps, in order. Do every dimension and every smell in it, even when the skill looks clean — a clean-looking file is what an unchecked smell looks like. Track progress by dimension so a partial review is visible as partial.

1. Static checks, early look. Run `scripts/static_checks.py <path>` to see mechanical results now (the finalizer re-runs them authoritatively at commit). A REF or BP hit on paths that are illustrations — in a skill that teaches skill-making, say — is a false positive: plan a Static override with a reason, not a finding. An LSB fail rests on an untested threshold (C05) — say so when reporting it.
2. Read `references/rubric.md` — dimensions, anchors, and per-smell definitions live there. Read every file in the target directory.
3. Judgment pass. Work through dimensions 1–5 in rubric order; check every smell in each against its definition. Before leaving each dimension, ask the absence question: what does this skill's job imply should exist in this dimension that is absent? The job is what the file itself promises — its description's claims and the situations its steps will hit — not generic best practice. Prompts, not required elements: a rule for a foreseeable conflict, a plan or review gate, a caveat for a known failure mode, a concrete spec where format matters. File an absence only when the missing guidance would change behavior on a task the description claims to handle — most dimensions in most skills have none. Absent guidance leaves no flawed sentence to notice; it is found by asking, not by reading alone. File it under the smell that names the gap (none quite fits — use the closest and mark it Uncertain), cite the span where the missing guidance belongs (the closest section or heading), anchor on text that is actually there, and name in Why the promise or step that implies the missing guidance. A finding records: smell ID, File, Lines (a span of at most 40 lines), Anchor (a few words verbatim from that span), Why it matters, a concrete Fix, and a blocker marker when the skill fails its job if this stands. No span, no finding — the finalizer extracts the real quote from your span and refuses evidence that isn't in the file. Unsure whether a hit is real — mark it Uncertain for the user to adjudicate; don't silently drop or assert it.
4. Cold-reader probe. The probe model — the one the user named, else any available cheap headless CLI — gets exactly two things: the fixed probe prompt from references/rubric.md, verbatim, and the full target SKILL.md. No session context, no other files, no improvised questions. Note its misreads. No probe model available — estimate and write "estimated".
5. Score all six dimensions 1–4 against the anchors. Pick the anchor that describes the file; there is no midpoint to split.
6. Finalize. Write the report (template below) to a scratch file, then run one of:
   - solo: `python3 scripts/finalize.py <report> <target>` — appends to ledger/runs.jsonl when the working directory has one, else prints the line for the user to file.
   - eval batch: `python3 scripts/finalize.py <report> <target> --outbox <dir> --batch-id <id> --batch-seq <n>` — one file per run; the orchestrator alone runs `--drain <dir> --ledger <file>` afterward.
   On VALIDATION ERROR, fix the report and rerun — errors are line-precise and say what was expected. Show the user the canonical report the script prints. If the review hit an output limit, declare it in Omitted-Findings — never truncate silently.

## Report template

This is the artifact you author; the finalizer prints the canonical human report from it.

```
# Review: <name> (<path>)

Reviewer-Model: <model id>
Reviewer-Effort: <effort>
Repeats-In-Batch: <n>
Probe-Model: <model, or the word estimated>
Omitted-Findings: <n, omit when 0>

## Findings

### F1 · <SMELL-ID> · blocker      <- " · blocker" only when it is one
File: <path relative to the target>
Lines: <N or N-M>
Anchor: <a few words verbatim from the span>
Why: <why it matters>
Fix: <concrete fix>
Uncertain: yes                     <- only when uncertain

## Scores
Trigger: <1-4>
Instructions: <1-4>
Grounding: <1-4>
Verification: <1-4>
Economy: <1-4>
Cold-Reader: <1-4>

## Probe-Misreads
- <what the cold reader got wrong, quoting its words, one bullet each — or the word none>

## Static overrides
- <CHECK>: drop — <reason>         <- only for false-positive static fails

## Notes
<free text, optional section>
```

Real example finding — verified: the finalizer extracted this quote from the pinned fixture fixtures/real/grill-with-docs/2026-07-13-697d4ce:

```
### F1 · CSD
File: SKILL.md
Lines: 3
Anchor: A relentless interview to sharpen a plan
Why: The description says what the skill does but has no when-to-use clause and no trigger keywords.
Fix: Add a when-to-use clause and trigger keywords to the description.
```

## Rules

- Never edit, move, or reformat the reviewed files — including fixing the flaws you found.
- Never write or edit a ledger line by hand; finalize.py is the only writer, in every mode.
- Every finding cites a span and anchor from the target. A finding whose evidence the finalizer cannot extract does not land.
- A clean pass on a smell is not a finding; report findings, not compliance.
- Fixture targets under fixtures/planted/ have a manifest beside the fixture directory. Never open it during review — it is the answer key. After the review, the user (or eval harness) compares findings to it.
