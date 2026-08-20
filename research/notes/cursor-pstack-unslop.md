# Cursor pstack `unslop`

- Source: Cursor `plugins`, `pstack/skills/unslop/SKILL.md`
- Pinned commit: [`99559f2f52047978602ef365589275831e76af07`](https://github.com/cursor/plugins/commit/99559f2f52047978602ef365589275831e76af07)
- Pinned file: https://github.com/cursor/plugins/blob/99559f2f52047978602ef365589275831e76af07/pstack/skills/unslop/SKILL.md
- Retrieved: 2026-08-21
- File SHA-256: `181883e539caec8258ec9129e3ba5f133409144a2cbf2aa361158ab94cfc3441`
- Git blob SHA: `2a93c06bbe54fde89a36c88e63ef07477da323d4`
- License: [MIT, copyright 2026 Lauren Tan](https://github.com/cursor/plugins/blob/99559f2f52047978602ef365589275831e76af07/pstack/LICENSE)
- One line: a 31-item recognition list for removing common AI-writing patterns; useful as candidate interview prompts, not as evidence or a contract to copy.

The GitHub Contents API supplied the pinned bytes. Decoding its `content` field and running `shasum -a 256` produced the hash above. This note paraphrases the source and copies no substantial passage. The license attribution remains here for provenance.

## Source argument

The source proposes a repeated editing loop: scan for known patterns, rewrite without changing meaning, and self-audit for remaining machine-like prose. It also says the skill should always apply and asks the editor to add personality after removing patterns.

Those are source positions, not local evidence. The list mixes coding-agent communication with article editing, marketing prose, typography, and general style advice. It does not test whether its patterns matter to this user, whether a recognition list improves an interview, or whether bans cause substitute habits.

## Candidate recognition catalog

These are prompts for an interview, not default bans. Show all six only in the catalog-assisted arm. Only entries the user selects may reach a generated contract.

| ID | Recognition prompt | Boundary |
| --- | --- | --- |
| U01 · Sycophancy | Do replies praise, validate, or agree before giving a reason or answer? | A direct yes/no answer or agreement supported by evidence is not sycophancy. |
| U02 · Canned framing | Do replies begin or end with stock assistant framing that carries no task information? | An opening outcome or a closing fact, status, or next action is useful content. Track opener and closer as sublabels. |
| U03 · Padding | Do replies use removable filler or stack two or more hedges on one claim? | One explicit hypothesis or uncertainty label required by evidence discipline is not a hedge stack. Track filler and hedge stack separately. |
| U04 · Forced triads | Do replies stretch two or four natural points into a group of three? | Three real, distinct items are not forced structure. |
| U05 · Empty conclusions | Does the ending repeat the response without adding a fact, status, decision, or next action? | A required recap that adds current status or evidence is not empty. |
| U06 · Unsupported claims | Do abstract, evaluative, or promotional words replace a mechanism, source, or number, including an `-ing` clause that asserts an unshown result? | A project term with a precise local meaning is not vague. An `-ing` form alone is not a hit. Track abstraction, promotion, and unsupported result as sublabels. |

For later adjudication, assign an overlapping span to the first matching entry in U01–U06 order. E-09 must freeze operational matchers and worked examples before any measured output is read.

## Take, test, reject

### Take into the research catalog

- The six recognition prompts above.
- The idea of asking about observed patterns rather than installing a full generic ban list.
- A separate substitute-tic check after a selected pattern is suppressed.

“Take” means retain as a candidate for testing. It does not mean adopt into `agent-voice`.

### Test before any binding use

- Whether the six prompts find more manifest-listed, user-relevant patterns than inventory plus unaided recall (C19).
- Whether any extra coverage pays for its contract size without irrelevant selections or task regressions (C20).
- Whether suppressing the same selected tics creates adjacent substitute habits (C21).
- Whether catalog-assisted contracts reduce the same manifest-wide set of user-relevant listed tics more than inventory-only contracts (C22).

### Reject from this catalog

- “Must always apply” and any automatic global activation.
- Adding soul, opinions, deliberate mess, or a persona.
- The full 31-item list.
- Blanket bans on punctuation, parentheses, title case, quotes, passive voice, adverbs, or fancy synonyms.
- Article- and marketing-specific checks such as media name-dropping, travel adjectives, and formulaic feature prose.
- False ranges: plausible in prose, but lower priority than the six categories approved for the first screen.
- The source's examples or confidence as evidence that any pattern matters here.

## E-09 boundary

- Compare a fixed inventory-only interview with the same inventory plus U01–U06. Keep the round count, contract template, task set, and all other instructions equal.
- Use a simulated interviewee that receives only a frozen preference manifest. Build the manifest with a no-context process from voice artifacts and corrections dated before 2026-08-21. Record the input hashes. Do not expose that process to this note or the source.
- Run both arms from the same frozen base tree. Remove this note, D-029, and C19–C22 from both views before any trial. Give only the U01–U06 table and its boundary column to treatment as an interview attachment. Record the base commit, shared view diff, attachment hash, and complete instruction stack for both arms.
- Use five trials per arm and family. Run Fable and Kimi as separate interviewer and generator families. Use deterministic matchers where possible and one fixed, blinded third-family judge for task success and substitute-tic judgment.
- Treat five runs as a preregistered screen, not a significance test. Record every run, the mean, and variance.
- Keep interview coverage separate from runtime task outputs. Normalize contract tokens after removing fixed template boilerplate.
- For substitution, add a paired suppression/no-suppression comparison using the same selected tic set, generator, and tasks. Freeze the substitute map and examples before reading outputs.

## Open risks

- Model pretraining may give the inventory-only arm high unaided recall, leaving a ceiling effect. Record its unaided list per trial.
- The six categories were chosen with local voice context. E-09 tests whether these prompts help; it cannot show that the upstream source discovered them independently.
- Recognition prompts may prime irrelevant selections. The frozen manifest, not this catalog, defines relevance.
- A simulated interviewee measures interviewer elicitation, not the full dynamics of a real user's changing preferences.
- Categories overlap. Frozen precedence and sublabels must prevent double counting.
- Existing voice rules can floor listed-tic counts. E-09 must use the frozen instruction stack named in its design.
- Suppressing one surface form may shift punctuation, phrasing, or structure instead of removing the habit.
- The upstream file can change. This note refers only to the pinned bytes and hash above.

## Claims

→ `research/CLAIMS.md` C19–C22.
