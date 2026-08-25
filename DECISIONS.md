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

## D-028 · 2026-08-20 · agent-voice has one owner per rule and validates before writing

Issue #1 repairs the contradictions introduced when D-025 and D-026 changed the original single-file delivery. The user chose one owner per voice rule: if a proposed migration is declined, the existing instruction file remains the sole owner and the equivalent rule is omitted from the contract. The hand-off names the retained owner and warns when a project-local rule therefore does not reach other projects. This scopes D-021's “a paraphrase never thins the contract” rule: the agent may not silently omit an equivalent rule, but an explicit user ownership choice can leave it outside the contract. It also fulfills D-026's no-duplication intent.

The default custom-output-style alternative is private: one project-named file under `~/.claude/output-styles/`, activated from the target's `.claude/settings.local.json`. A team-shared project style remains possible only after the user accepts that its rules and setting affect contributors. If a user core is already loaded, the style omits those owned rules. Claude Code supports both user and project output-style scopes and local project activation; checked against the official output-style documentation on 2026-08-20.

The default rules delivery now has separate core and delta templates. Approval is per migration in one diff pass. The approved effective voice stack is validated and cold-read from scratch before any live write, then the installed files are validated again. `validate_artifacts.py` owns mechanical checks for rules, output styles, settings, derived append files, and exact cross-file duplicates; paraphrase ownership stays a judgment step. Fable 5 High and Kimi K3 independently reviewed the repair plan and validator as context; neither review is effectiveness evidence.

## D-029 · 2026-08-21 · `unslop` is a six-prompt research catalog, not a rule set

Cursor pstack's `unslop` enters as one pinned source note and four untested claims, never as local evidence or binding `agent-voice` text. Its 31 checks are reduced to six recognition prompts relevant to coding-agent communication: sycophancy, canned framing, padding and hedge stacks, forced triads, empty conclusions, and unsupported abstract, promotional, or `-ing` result claims.

The catalog is opt-in twice: it appears only in the catalog-assisted interview arm, and only entries the user selects may reach a generated contract. “Must always apply,” adding soul or persona, blanket punctuation and prose-editing bans, false ranges, and the rest of the general editorial list stay out. A later experiment may reverse a rejection only with recorded local evidence.

The catalog composition and E-09 guardrails are durable. The guardrails are a no-context manifest derived from pre-source artifacts, two isolated views of the same frozen base with only treatment receiving the six-row catalog, five trials per arm and family as a screening batch, Fable and Kimi as separate model families, and the C19–C22 falsifiers. E-09's exact artifact selection, base commit, model versions, seed schedule, matcher implementation, judge model, and adjudication cutoffs remain run-scoped and belong in its frozen design, not this file. Fable 5 High and Kimi K3 challenged the plan as context; their useful findings shaped the user-approved scope but are not effectiveness evidence.

## D-030 · 2026-08-21 · PR state follows readiness unless the user directs it

An explicit user instruction controls whether a PR is draft or ready. Without one, a PR stays draft only while work is incomplete. Mark it ready as soon as its planned implementation, validation, and pre-PR reviews are complete. A publishing tool's draft default does not delay that transition.

Haiku cold-read the final rule with no repository or session context. It correctly handled incomplete work, completed work, explicit draft and ready instructions, later overrides, and a publishing tool's draft default. It found no contradiction.

## D-031 · 2026-08-21 · Cold-reader gate records are not measured experiment results (amends D-023)

`type: experiment` has two documented shapes. Measured results use an exact numeric experiment ID such as `E-07` or `E-09`, carry effect statistics and artifact hash pins, and may support claims under D-023. An ID with the `-cold-reader` suffix is never a measured result. Rows with `experiment: E-09-cold-reader` are precondition records: they may allow or block the start of later measured execution, but they never supply outcome data. They have two tiers. Exactly four append-only legacy rows use `tier: smoke`; the current harness never writes another smoke row. Their complete canonical rows are pinned, and no gate reads them. The E-09 harness writes `experiment: E-09-cold-reader, tier: qualification` once per completed reader-profile batch. For each new required reader profile, the verifier and gate derive the exact row fields, counts, content-addressed run id, raw path, and key object. The key contains `tier: qualification`, the profile name, and the SHA-256 of that profile, `harness.py`, `catalog.json`, `cold_reader_cases.json`, and `freeze.json`. The append-only trusted ledger preserves older qualification rows after those inputs change. The verifier checks their exact row shape, key shape, count consistency, raw path, timestamp, pass state, and run id without comparing them with newer input bytes. An older row can never authorize a newer freeze. Before measured execution, the gate requires the qualification namespace to resolve to its lexical path beneath the repository. It regrades every frozen case record and checks its schema, assertions, retry record, persisted provider identity, timestamps, complete namespace inventory, start marker, summary, and derived ledger row. The exact current row must be an uncommitted ledger addition. A missing, committed-only, malformed, historical, failed, incomplete, or non-regrading qualification blocks measured calls. These local records are an integrity gate, not provider-signed proof against a hostile local writer. Consumers must exclude every `E-09-cold-reader` row from claim, score, and experiment-effect aggregates.

The composite discriminator preserves history without confusing gate state with outcome evidence. Every writer remains code-owned; agents never assemble ledger lines by hand.

## D-032 · 2026-08-24 · Measured raw records live in immutable releases (amends D-023)

Here, `freeze_sha256` is the SHA-256 of the frozen `freeze.json` bytes. The measured batch id hashes the complete validated freeze object, including its UTC creation date and file map. A compact result is a schema-2 object. Its `lines` array equals every and only ledger row whose `results_path` names that file.

For measured batches created from this decision onward, Git stores the frozen design, harness, packager, verifier, expected inventory, committed manifest, compact results, claim updates, and ledger lines. The full raw directory is ignored staging. One deterministic `.tar.gz` and one manifest are uploaded to a draft GitHub Release. The released and committed manifest copies must have identical bytes. Publication is a separate human-confirmed action. Repository immutable releases must be enabled before staging. `stage-release` checks the repository setting through the GitHub API and refuses to create or resume a draft when it is disabled.

The release tag is unique and resolves to the exact frozen commit already contained in the default branch. The exact frozen commit is the commit that last changed `freeze.json`; qualification, measured calls, packaging, both release commands, and finalization require `HEAD` to equal it. Before the qualification or measured gate reads a frozen input, it matches the working `freeze.json` and every frozen input byte to that commit. Before any qualification provider call, the harness creates the exact qualification namespace beneath the repository and rejects redirected parents, links, and non-directory path components. Before each measured phase can call a provider, it creates the exact measured namespace and applies the same path checks. A non-empty namespace requires regular metadata that matches the current freeze, commit, and interview schedule. Later phases also require their stored schedules to match recomputation. A partial qualification namespace stops before any provider call. Before any reader or adapter smoke provider call, the harness creates and validates the exact keyed base and new attempt namespaces. The adapter key binds the harness, model registry, prompts, and case suite. Reader and adapter smoke attempts are selected without reading their summaries; the gate validates their namespace and inventory before the summary read. `artifact-pack`, `stage-release`, `publish-release`, and `finalize` each require the current packager and every provenance file to match that frozen commit byte for byte. `verify-local` checks only the archive and manifest; it does not replace that frozen-source check. Frozen `freeze.json` defines the complete provenance key set; the plan and manifest cannot remove entries. The manifest pins the repository by numeric id and name, the repo-relative raw root, frozen schedule hashes, the frozen and packager commits, every frozen input hash, every archive member hash and kind, expected and actual counts, exclusions, errors, retries, the sanitization report, and an explicit `supersedes` value or null. Inventory counts include every planned record, including failures and exclusions; separate status counts preserve those outcomes. Failed and excluded records cannot carry a result. Record-manifest paths must be safe regular files inside the measured namespace. Every start and completion event has an exact schema and a run id derived from that namespace and event payload. A retry never repeats a durably started call: it hashes an existing immutable record or writes a terminal `interrupted` record when the record is absent. The packager revalidates each successful record's requested model, allowed reported models, required or configured provider, and documented Codex identity evidence against the frozen profile. The frozen Codex minimum version is enforced before every execution. `adjudication-pending.json` and `adjudication-resolved.json` exist exactly when the two substitute judgments disagree. The pending file must equal those current disagreements. The resolved file contains one valid verdict list for every and only current disagreement blind ID. The packager admits only the exact expected set of regular JSON or JSONL files. Every document and decoded nested JSON string must use strict JSON: duplicate object keys and non-finite numbers are forbidden. It rejects links, unsafe POSIX or Windows paths, malformed data, unexpected or missing members, and every nonempty configured credential value found as exact bytes or inside a decoded JSON string. It decodes nested JSON strings until none remain. A decoding resource limit fails closed. It applies each frozen forbidden regular expression to the encoded JSON text and every decoded JSON string. The sanitizer report hashes the credential-variable names and complete forbidden-pattern definitions as one policy. Release commands rederive that policy from its source file at the frozen commit; a coordinated plan and manifest edit cannot weaken it. Any credential or pattern match blocks publication. There is no waiver; correct the frozen sanitizer or inventory and start a new batch. The archive verifier requires sorted member order and byte-for-byte reproduction by the deterministic packer, including its normalized tar fields, compression level 9, timestamp zero, and OS byte 255. Archive and manifest writes use same-directory temporary files and atomic no-overwrite installation; an identical retry repairs an interrupted pair.

The seven stages are package, verify locally, stage the draft, inspect the draft, publish, verify remotely, then finalize. Packaging writes a local plan for inspection. For E-09, `stage-release` and `publish-release` each independently run the frozen harness, derive a fresh plan, and require exact equality with that saved plan before contacting GitHub. Plan equality authenticates the expected execution, exclusions, and inventory. Each command then separately requires the manifest and current raw inventory and member bytes to match its fresh derived plan. A raw change between the commands makes `publish-release` fail. Before any GitHub contact, publication rejects a conflicting tracked-manifest copy. Before the irreversible publish action, it queries GitHub and rejects any existing tag that does not resolve to the frozen commit. Any failed check exits nonzero before draft creation or publication. Inspection is not a sample: the operator reviews every recorded error, retry, and exclusion, plus all count, sanitizer, and digest summaries. `publish-release` performs stages five and six in one command. Stage six is its automatic first fresh-download and GitHub release- and archive-attestation verification after immutability; it is not `finalize`. The remote verifier requires the release commit to remain contained in the repository's current default branch. It fetches the provenance index, every named source, and the sanitizer policy from that commit through GitHub and matches their bytes to the manifest. It rejects a linked source even when GitHub resolves it to the target's bytes. The command then copies the released manifest bytes into the tracked path. The stable ledger subjects are the repository id, release id and tag, plus the archive asset name and SHA-256. Stage seven is the separate `finalize` command. Immediately after the fresh download and again before any result or ledger write, it requires the current packager and provenance bytes to match the frozen commit and the current raw inventory and member bytes to match the derived plan and manifest. The compact result contains exactly the full ledger row set for its path. Each ledger row's freeze hash must equal its manifest. Pull-request code tests run only on the ordinary `pull_request` event and receive no release credential. The separate `pull_request_target` job runs only the base-branch verifier, uses a read-only token, requires the checked-out merge commit and its second parent to match the event's merge and head SHAs, requires both the GitHub-verified numeric repository id and current repository name, cross-checks ledger pins, and remotely verifies every candidate release reference. It treats the candidate checkout only as data. The trusted plan checker never executes a harness from an external root. The candidate ledger must be a byte-for-byte append-only extension of the trusted base ledger. Every exact numeric experiment row requires this evidence shape except `r-20260817-4cccea322c`, `r-20260817-8fbcc01b2b`, `r-20260817-d4d49120dc`, and `r-20260817-48eac1a620`. Those four rows are pinned by their complete canonical hashes. Trusted code registers the complete schema and content-addressed run-id rule for each post-D-032 numeric experiment. For E-09 it rederives arm summaries, rates, paired differences, counts, and claim checks from the five ordered run records; hashes the canonical completion timestamp with the rest of the row payload; and requires exactly one row for each frozen model family. An unregistered numeric experiment, malformed row, duplicate family, or derived-value mismatch fails. Every other row's experiment, batch, freeze, manifest path, result path, complete result row set, canonical identity, and remote receipt must all agree. CI downloads releases referenced by the ledger once. It enumerates every committed `experiments/*/artifacts/*.json` path regardless of file type, rejects non-regular paths, then remotely verifies manifests that no ledger row names. Main-branch CI repeats the same checks against the previous main ledger. A transient or interrupted command is retried with the identical plan, raw root, archive, manifest, and tag. A content or policy failure requires a corrected freeze and new batch. A bad published bundle is never replaced: the new batch names the old release in `supersedes`. Unpublished or abandoned work is not evidence and does not use `supersedes`.

No external mirror is required in v1. We accept GitHub availability risk; the committed manifest makes loss detectable, not recoverable. The tooling never deletes local raw staging. A later manual deletion is a separate operator decision after release and manifest verification; this policy neither requires nor automates it. E-07, E-08, and existing E-09 smoke and qualification artifacts are unchanged. Small smoke records stay in Git: retain the four legacy reader smokes. For each content-addressed current reader or adapter key, retain only its highest numbered `attempt-NNN` directory before opening a PR.

After this policy merges and before the first measured E-09 provider call, run the publication lifecycle through stage six from the merged exact frozen commit on a synthetic one-record raw root. Stage seven remains the measured E-09 finalizer and does not run in this smoke. Use a unique `artifact-storage-smoke-<frozen-sha-prefix>` release tag. The smoke manifest uses `experiment: artifact-storage-smoke`; it is not measured evidence and creates no result or ledger line. The smoke carries its own frozen provenance index, sanitization policy source, and plan generator under `experiments/artifact-storage-smoke/`, because the trusted plan check pairs `experiments/e09/freeze.json` with E-09 alone. Commit the published manifest copy so CI's orphan pass keeps verifying the release. Record the immutable release URL, tag, archive and manifest SHA-256 values, remote receipt, and outcome on issue #10. Close that issue only after the fresh download and both attestations verify. Retain the local smoke root; do not commit it.
