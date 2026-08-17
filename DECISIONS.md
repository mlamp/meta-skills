# Decisions — durable record

One short entry per decision: what was decided and why. Newest at the bottom. Reverse a decision by adding a new entry that marks the old one superseded — never by rewriting what was decided. Wording may be compressed later if meaning, numbers, dates, and order stay unchanged (D-018).

## D-001 · 2026-07-21 · Repo purpose and working style

This repo holds meta-skills: skills that review and improve other skills and agentic tools. Binding text must use plain english and be clear in one pass. Give the user options and a recommendation for important choices. Record the outcome here when it is made, not at session end.

## D-002 · 2026-07-21 · Layout: skills/ and symlink promotion

Author skills in `skills/<name>/SKILL.md`. Frontmatter status is `draft`, `testing`, or `proven`. Make proven skills available everywhere through a symlink in `~/.claude/skills`.

This is the smallest structure that works everywhere and remains easy to change later. No plugin-marketplace scaffolding before the first skill exists. No project-local `.claude/skills` — those skills are unavailable elsewhere.

## D-003 · 2026-07-21 · Research has three layers

Raw PDFs go in `research/sources/` (ingestion only). One distilled note per paper goes in `research/notes/` (the read layer). Every borrowed idea goes in `research/CLAIMS.md` with status `untested`, `testing`, `validated`, or `refuted`, plus the test that would change its status.

Research is unproven input. Treat nothing from a paper as true until it is validated here.

## D-004 · 2026-07-21 · Claim hygiene

An effectiveness claim in binding text must cite our own evidence — a D-number, a ledger entry, a fixture result. Otherwise mark it `[UNVERIFIED]` and add `Falsifier:` naming the recorded result that would prove it wrong. A tag without a falsifier does not count.

## D-005 · 2026-07-21 · Cold-reader probe

New skill or rule text lands only after a model with no session context correctly restates its obligations. Fix or consciously dismiss every misread.

First applied to this repo's `CLAUDE.md`: Kimi K3, headless, file piped in, no session context. All four scenario questions correct, no misreads.

## D-006 · 2026-07-21 · Fixtures and run records from day one

Every skill run should leave a record. Design the ledger schema and location with skill #1, once its output is known.

`fixtures/` holds the eval corpus from day one: real `SKILL.md` files and planted-defect files whose flaw manifests make recall measurable. Scores use repeated runs. When a score matters, also use a second model family.

The repeated-runs rule was a prior, not a result — the claims behind it, C10 and C11, were untested when this was decided.

## D-007 · 2026-07-21 · Real fixtures are pinned snapshots

Copy each real fixture unchanged from a pinned upstream commit into `fixtures/real/<name>/<commit-date>-<sha7>/`. Add `PROVENANCE.md` with the source, path, license, full SHAs, and re-fetch commands.

Never change a snapshot. A newer upstream state gets a new snapshot directory. Where upstream history moved, keep a pair — oldest useful plus current. The pairs are the first probe for C07.

First corpus:

- `grill-with-docs` and `tdd` from `mattpocock/skills`, MIT, version pairs. Both were sharply reduced upstream; `grill-with-docs` is now a seven-line alias to sibling skills.
- `karpathy-guidelines` from `multica-ai/andrej-karpathy-skills`, ~195k stars, no license, unchanged upstream since 2026-01-28. Vendored while this repo is private; the license must be resolved before any public push.

Pinned snapshots keep recorded results stable. Provenance keeps every snapshot auditable and re-fetchable.

## D-008 · 2026-07-21 · Check fixture licenses per skill

Verify the license of each skill directory before vendoring — one repo can mix terms. When upstream ships a per-skill license, it rides inside the snapshot. Otherwise a repo-level copy lands at `fixtures/real/LICENSE-<source>.txt`.

`anthropics/skills` has no top-level license. Its example skills carry Apache-2.0 `LICENSE.txt` files. Its document skills — `pdf`, `docx`, `pptx`, `xlsx` — use a source-available license that forbids retaining copies, reproduction, derivatives, and distribution. Never vendor them, even in a private repo.

Corpus adds under this entry, all version pairs: `frontend-design` and `skill-creator` (`anthropics/skills`, Apache-2.0); `writing-skills` and `test-driven-development` (`obra/superpowers`, MIT).

Considered and not taken, re-openable: `claude-api` (heavy, 66 files), `mcp-builder` (no unique gap), `brainstorming` (churn is app plumbing, not skill text), `affaan-m/ECC` (no new structural axis).

## D-009 · 2026-07-21 · Skill #1 is review-skill

`review-skill` reviews a full skill directory: `SKILL.md`, references, and scripts. A lone `SKILL.md` is accepted; directory-dependent checks are then reported as skipped, never guessed.

Output: findings — each with smell ID, location, evidence quote, why it matters, and a concrete fix — plus rubric scores and a ledger entry. The reviewer never edits the reviewed files.

Not in v0: applying fixes (a separate skill's job), measuring runtime effectiveness (the eval harness's job), and reviewing non-`SKILL.md` artifacts such as `CLAUDE.md` or agent definitions. Transcript input was also rejected for v0 — no fixture has transcripts; revisit when our own skills have ledger history.

The name is verb-first and does not collide with the built-in `/review` command for GitHub pull requests.

## D-010 · 2026-07-21 · Cold-reader probes are optional and configurable

A review includes a cold-reader probe: a cheap model with no context restates the skill's obligations, and the restatement is scored.

Use the model the user names, such as `cold-reader: haiku headless`. If none is named, use an available cheap headless model. If none is available, estimate cold-reader comprehension by judge and mark it explicitly as estimated.

The probe is optional so the skill still works where no second model exists. It stays in v0 because it mechanizes D-005 as a rubric check.

## D-011 · 2026-07-21 · review-skill rubric v0

Two layers.

Layer 1 is a mechanical pass/fail script in the skill directory. It checks: body at most 5,000 words (threshold from C05, untested), name at most 64 characters, description at most 1,024 characters, no backslash paths, no XML in the description, frontmatter parses with `name` and `description` present, referenced files exist on disk.

Layer 2 scores six judgment dimensions from 1 to 4 against written anchors, with no midpoint:

- Trigger and description: CSD, USN, NTPD, MUR — weighted first, per C12 and C04.
- Instruction quality: TSW, SOC, TOB, MDT, MT — per C08.
- Grounding and examples: ME, TSS — per C09.
- Verification and safeguards: NVS, EWP, NAH, RL, NPT, NG, BG, MC.
- Context economy and delegation: UD, MUS, plus a soft length judgment.
- Cold-reader comprehension, fed by the D-010 probe.

Every judgment finding is binary: present with a smell ID, location, evidence quote, and fix, plus one blocker flag meaning the skill fails its job if unfixed.

Rejected: a flat 26-smell checklist (no readable verdict), the paper's 10 groups as dimensions (uneven), 1–5 or 3-level scales (midpoint hiding), and severity ladders (unanchored judgment that varies run to run).

## D-012 · 2026-07-21 · Ledger schema and evidence threshold

Runs are append-only lines in `ledger/runs.jsonl`. A line is never edited. Repeated runs of one review share a `batch_id`. Schema documented in `ledger/README.md`.

Fields: `run_id`, `batch_id`, `date`, `target {path, fixture, snapshot}`, `reviewer {skill, version_sha, model, effort}`, `repeats_in_batch`, static results, `findings [{smell_id, location, evidence, blocker, fix}]`, scores per dimension, `probe {model, misreads}` or `{estimated: true}`, `vs_manifest {recall, precision, adjudications}` for planted fixtures, `notes`.

A score may be cited as evidence only from a five-run batch with variance. Ad hoc reviews may be single runs, marked `repeats_in_batch: 1`, and are never cited as evidence.

## D-013 · 2026-07-21 · Planted fixtures and hidden manifests

Build each planted fixture from a permissively licensed real snapshot. Plant about 10–12 deliberate flaws: at least one per judgment dimension, at least two static.

The manifest lives beside the fixture directory, never inside it. The reviewer reads the whole directory and must not see the answer key.

Recall = planted flaws caught / planted flaws. Precision = (planted + user-confirmed pre-existing findings) / all findings. Real bases carry about 10 pre-existing smells (C02), so off-manifest findings are adjudicated, never auto-counted as false positives.

Never derive from an unlicensed source. Never author a "clean" base from scratch — unlabeled pre-existing smells would silently corrupt precision.

## D-014 · 2026-07-21 · review-skill landed as draft

`review-skill` landed at `skills/review-skill`, status `draft`, after passing both kickoff gates: a self-review (run `r-20260721-001` in the ledger — three non-blocking findings, all fixed in-session) and a clean cold-reader probe (Kimi K3 headless, `SKILL.md` only, seven scenario questions, no misreads).

First planted fixtures: `tdd-p1` and `frontend-design-p1`, 12 flaws each, manifests sibling to the fixture directories. Static plants were verified to trip the checker. The checker also got a fix (trailing-backslash directory paths) and a caveat: illustrative paths in teaching skills can false-positive the REF check, so the skill now says to confirm REF and BP evidence in context.

Experiments E-01 through E-05 queued in `docs/experiments.md`. No claim status moved — nothing had been measured yet.

## D-015 · 2026-07-21 · Ledger v2 compiles reports into records

Supersedes the writer mechanics of D-012 (schema intent stands) and amends D-011's evidence rule.

The model authors exactly one artifact per review: a markdown report in a fixed template. It then runs `scripts/finalize.py`.

`finalize.py` parses the whole report — unknown, duplicate, or stray content is a loud, model-actionable error. It validates scores and smell IDs. For every finding it extracts the evidence itself from the cited file, line range, and anchor snippet; an anchor mismatch fails with nearby-line hints, so a hallucinated finding cannot enter the ledger. It re-runs static checks instead of trusting transcription. It generates all machine facts — content-addressed `run_id`, timestamp, reviewer git SHA, target file SHAs, `schema_version` — and serializes with `json.dumps`.

Commit paths: with a ledger present, direct append with `O_APPEND` plus `fsync` and duplicate-`run_id` refusal. Parallel batches use `--outbox`, one file per run, with a single `--drain` step as the only shared-ledger writer. `--print` when neither exists.

Truncation is never silent (`omitted_findings`). The model never writes JSON, run IDs, dates, or SHAs.

Three independent advisors — a second-family model, a third-family model, and web evidence — converged on this design. Measured free-hand JSON failure rates run 5–10%, against under 0.1% for enforced paths; our own first ledger line carried a model-invented placeholder timestamp. Hash chains and commit receipts are deferred until the first recorded incident.

Rule of thumb, kept: the probabilistic component authors; the deterministic component frames, verifies, and commits.

## D-016 · 2026-07-21 · DECISIONS.md stores durable decisions only

An entry belongs here only when future work must follow it or consciously reverse it.

Run-scoped calls do not belong here. Fixture picks, probe models, and batch names live in ledger lines, batch IDs, and experiment notes.

Set when E-01 setup was about to record its second-family fixture pick as an entry. `CLAUDE.md` was changed from "every decision lands in DECISIONS.md" to the durable-decision rule — the old rule was fixed, not caveated.

## D-017 · 2026-07-21 · Adjudication records and hidden spans

Planted-fixture results land as ledger lines with `type: adjudication`, one per batch, referencing its `run_ids`. Each records per-flaw catch rates, recall and precision after user verdicts, pairwise-Jaccard agreement, flip lists, score variance, and every adjudication verdict.

Only `ledger/adjudicate.py` writes adjudication lines. It matches a finding to a flaw when the smell ID is equal and the cited span overlaps the flaw span in `fixtures/planted/<name>.spans.tsv`, or when the static check ID matches. Everything unmatched goes to the user; verdicts are `flaw:<n>` (near-match credit), `pre-existing`, or `fp`. The script does all arithmetic and serialization and reuses the append guard from `finalize.py`.

The ledger writer rule is now: `finalize.py` writes review lines, `adjudicate.py` writes adjudication lines, nothing else writes anything.

Spans TSVs sit beside the manifests with the same answer-key status: never shown to reviewers, never edited after a recorded result references them.

First used in E-01: `adj-20260721-aeea8221b2`, `adj-20260721-0beccec7a6`, `adj-20260721-b58423aa64`.

## D-018 · 2026-07-21 · One-time tidy of this file

Every entry above was rewritten in plain english and compressed. Numbers, dates, order, and meanings are unchanged; git history keeps the originals. The header rule now allows this kind of compression; reversals still require a new entry. The first draft came from a second-family model and was reviewed and corrected entry by entry here.

## D-019 · 2026-07-21 · Absence pass and fixed cold-reader probe (amends D-011)

E-01 measured two reviewer defects: every pure deletion of real guidance was missed by every run (the rubric only interrogated present text), and cold-reader was the only dimension with score range 2 across identical runs (probe questions were improvised per run).

The judgment pass now ends each dimension with the absence question — what does this skill's job imply should exist here that is absent? — and an absence finding cites the span where the missing guidance belongs. The cold-reader probe uses a fixed five-question prompt in the rubric, verbatim, never improvised. Two cues sharpened: an absent output spec files as MT, not ME; NTPD requires an explicit first- or second-person pronoun, so imperative descriptions ("Use when…") don't count. First validation: E-06.

## D-020 · 2026-07-23 · Spot-check adjudication mode (amends D-017)

Real fixtures have no manifest, so E-02 added a spot-check mode to `ledger/adjudicate.py` — still the only adjudication writer. `spot-match` clusters every finding of a batch deterministically (same smell + same file + overlapping spans, ±2 lines, canonical order) and emits a digest-bound worksheet; `spot-commit` re-derives everything from the ledger, consumes only the verdict and note columns, and writes one `mode: spot-check` adjudication line per batch.

Verdict vocabulary: `fix-worthy | not-fix-worthy | wrong-evidence`. Strict precision counts fix-worthy alone as a true positive; grounded precision also counts not-fix-worthy; the two other verdicts stay separate in the record because they diagnose different failures (calibration vs grounding). Recall and manifest fields are absent from spot-check lines, never zero. One live spot-check line per batch; corrections are a new line naming the old one in `supersedes`, never an edit.

Design validated per the user's instruction by a council of three independent models — a clean Fable 5 xhigh headless run, codex, and kimi-k3 — given the same neutral brief; all three chose extending adjudicate.py over a committed verdicts file, converging on the digest guard, the closed vocabulary, and fix-worthy-only strict precision. Gate: planted-mode `match` output byte-identical on all five prior batches before commit (fe16ac6).

## D-021 · 2026-08-18 · Skill #2: agent-voice, a communication-contract generator

Source: disler/fixing-smartass-opus-5 (note: research/notes/disler-fixing-smartass-opus-5.md; claims C13–C17, all untested). The user's calls: deliver as a Claude Code custom output style with `keep-coding-instructions: true` (a custom style otherwise replaces the built-in engineering instructions), the portable append-system-prompt file derived on demand and never edited; land as draft and measure later (E-07, banned-phrase suppression first); interview-driven output with a minimal default.

Design reviewed by codex and kimi-k3 on the same brief. Adopted from both: the mirror is a derived artifact, not a second source of truth; no hook tier in v1; a contradiction with the existing stack stops for a user decision, while a paraphrase elsewhere never thins the contract; and one or two do/don't example pairs join the minimal default — this amends the approved "examples opt-in" default because both reviewers and our own read rank examples as the source's strongest component. Rejected: dropping the interview opt-ins, a provenance data model, drift detection in v1.

Routing rule the skill encodes: anything a setting controls deterministically goes to settings, never prose. First case: `"attribution": {"commit": "", "pr": ""}` replaces the source's "never add a co-author" prompt line.

Ledger: agent-voice runs write a minimal `type: "generation"` line via the skill's own finalize script, documented in ledger/README.md; the schema stays minimal until real runs show what matters (pattern of D-006).

## D-022 · 2026-08-18 · agent-voice reframed as a theory test; second source distilled

The effort is generalized past its trigger material. The problem: frontier coding models spend output on prose nobody asked for — tic phrases, recap bloat, widened scope, mid-task check-ins — costing tokens and reader time; whether the cause is model training or harness is an open hypothesis we don't need in order to test the lever. The theory: behavior wanted on every turn belongs at the most persistent layer available (setting > system-prompt layer > context files). agent-voice packages that theory for reuse across projects; it is not a port of any one author's prompt. Theory doc: docs/communication-contracts.md.

Second source added: the user's own collected production practice — writing-for-humans prose rules, evidence discipline, anti-pause drive rules — distilled into research/notes/collected-writing-for-humans.md with origin projects unnamed. It adds reader-priority patterns to the default template, an opt-in Drive section, and C18 (drive rules reduce mid-task checkpoints — untested). The CLAIMS.md section header now names the theory doc and both source notes instead of a single upstream repo.

## D-023 · 2026-08-18 · experiments/ directory and the experiment ledger line

Experiment harnesses and their raw outputs live in `experiments/<e-xx>/` — design.md frozen before the measured runs, tasks and harness beside it, raw responses kept as evidence. Results land in ledger/runs.jsonl as `type: "experiment"` lines, one per family per experiment, written only by that experiment's harness script. The line carries per-arm per-task stats plus sha16 of the contract, harness, and task files, so the measured artifacts are pinned. First user: E-07.

## D-024 · 2026-08-18 · AGENTS.md is a symlink to CLAUDE.md

One instruction file for every harness: CLAUDE.md is the real, canonical file (Claude Code sessions edit it), and AGENTS.md is a committed symlink to it for harnesses that read AGENTS.md (codex, cursor). This direction is deliberate — the file that gets edited is real, so an editor can never break the link by saving. Reverse of the convention some projects use; here the editing traffic is on CLAUDE.md.

## D-025 · 2026-08-18 · agent-voice delivery default: rules file (amends D-021)

E-07 and E-08 refuted the system-prompt-placement advantage the output-style delivery rested on (C17: placements indistinguishable single-turn and at ~37k context tokens, both families; the contract itself works at both depths). The user chose the simpler layer: default delivery is now `.claude/rules/<name>.md` in the target project (user-level `~/.claude/rules/` for a personal scope), with the custom output style demoted to an interview option — its `keep-coding-instructions: true` rule unchanged — and the portable append file still derived on demand. Caveat recorded in the skill: the tested arm was CLAUDE.md itself; the rules directory is the same always-loaded layer but was not its own arm. Reopen with C17 if 100k+/post-compaction regimes ever show a placement gap.

## D-026 · 2026-08-18 · agent-voice v2: two layers and migration (amends D-025)

The contract splits by ownership, since placement is free on the evidence (C17 refuted). A user-level core at ~/.claude/rules/ carries the personal voice — banned phrases, response shape, generic boundaries, drive — and follows the user everywhere without imposing on teammates. A per-project delta at .claude/rules/ holds only what the core doesn't say: example pairs, migrated rules, team-agreed norms, project terminology. The split test for any line: wrong or meaningless in the user's other repos → project; true everywhere → core. A delta with nothing to say is not written.

The inventory now classifies existing instruction text as voice-shaped or project-factual, and the skill proposes migrating voice-shaped rules out of the project's own instruction files into the contract — diffs on both files, user-approved, never silent — so the contract replaces duplication instead of adding a parallel copy. Known limit recorded: user-level rules don't reach harnesses that read only the repo (AGENTS.md) or wrappers with their own config dir.

## D-027 · 2026-08-18 · Public: README entry point, MIT, license gate resolved

The repo goes public on GitHub (mlamp/meta-skills). Root README.md is the entry point for humans and agents: the evidence headlines with ledger ids, and three adoption paths for agent-voice — fast path (copy the contract), full flow (a fetch-and-follow prompt any harness can run, told to skip the home-repo ledger step), and casual cherry-pick (review-and-propose). Own content is MIT; vendored fixtures keep upstream licenses. The one pre-registered blocker (D-007: karpathy-guidelines, no upstream license) is resolved by the listed drop path — snapshot files removed, PROVENANCE keeps the pinned SHAs and re-fetch command, the E-02 ledger line stays valid.
