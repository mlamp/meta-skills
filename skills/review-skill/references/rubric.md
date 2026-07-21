# review-skill rubric

Two layers (D-011). Layer 1 is mechanical and scripted. Layer 2 is judgment: six dimensions, each scored 1–4 against the anchors below, findings tagged with smell IDs. Smell IDs and definitions derive from the 26-smell catalog in arXiv:2607.01456; their fix-worthiness here is claim C01 [UNVERIFIED]. Falsifier: fixture reviews where user adjudication puts precision of catalog-based findings under ~70% (C01 test).

## Layer 1 — static checks

Run `scripts/static_checks.py <path>`. Checks: FM-parse (frontmatter parses, name and description present), LSN (name ≤ 64 chars), LSD (description ≤ 1,024 chars), XID (no XML/HTML tags in description), LSB (body ≤ 5,000 words), BP (no backslash paths), REF (files referenced in the body exist on disk; skipped for a lone SKILL.md).

The 5,000-word cap is C05 [UNVERIFIED]. Falsifier: the C05 A/B — a long skill vs its distilled variant on the same tasks — showing no outcome difference. An LSB fail becomes a finding automatically at finalize, like every non-overridden static fail — don't file it by hand too; note in the report that the threshold is untested.

## Layer 2 — dimensions and anchors

Score every dimension every review. Pick the anchor that describes the file; there is no midpoint. A finding requires an evidence quote; no quote, no finding.

Every dimension's smells cover absences as well as flaws in present text. Good present text does not clear a dimension: before leaving each one, ask what this skill's own job — its description's claims, the situations its steps will hit — implies should exist there that is absent (E-01: every pure deletion of real guidance was missed by every run that only read what was on the page). File an absence only when the missing guidance would change behavior on a task the description claims to handle; most dimensions in most skills have none. An absence finding cites the span where the missing guidance belongs and anchors on text that is actually there.

### 1. Trigger & description — smells CSD, USN, NTPD, MUR

Weighted first: divergence concentrates at the first decision (C12), and description form drives invocation (C04) — both [UNVERIFIED]; falsifiers are their CLAIMS.md tests.

- 4: Description states what the skill does, when to use it, and carries trigger keywords; the name states the capability; third person; usage rules present wherever behavior depends on situation. A router would fire on target tasks and stay quiet on neighbors.
- 3: Form present but one element weak — thin keywords, vague when-clause, or usage rules missing where behavior forks.
- 2: A required element absent or misleading; triggering depends on the user already knowing the skill exists.
- 1: Name or description wrong for the job; a router would misfire routinely, in either direction.

### 2. Instruction quality — smells TSW, SOC, TOB, MDT, MT

Instruction text is the biggest debt magnet (C08 [UNVERIFIED]; falsifier: its CLAIMS.md category-count test).

- 4: Work decomposed into steps at the right altitude — objectives with defaults, decision guidance at every real fork, an output template wherever format matters. No command transcripts, no undifferentiated option lists.
- 3: Mostly stepwise and clear; one section prose-blobbed, one fork without guidance, or one missing default.
- 2: Several violations — workflows in prose blocks, option buffets, or brittle hardcoded command sequences.
- 1: Unfollowable without guessing: no steps, no defaults, or contradictory instructions.

### 3. Grounding & examples — smells ME, TSS

Placeholder examples rot into debt (C09 [UNVERIFIED]; falsifier: its CLAIMS.md test).

- 4: Every claim or format that an example would change behavior on has a real, task-specific example; nothing silently goes stale.
- 3: Examples present but one is thin or generic; minor staleness risk unflagged.
- 2: Key behavior unanchored — a missing example where format or style matters, or placeholder examples.
- 1: Placeholders throughout, or stale content presented as current.

### 4. Verification & safeguards — smells NVS, EWP, NAH, RL, NPT, NG, BG, MC

- 4: Outputs have a validation loop; complex tasks plan before executing; a human-escalation point exists; required steps carry do-not-skip guards; long workflows track progress; warnings are surfaced, caveats resolved.
- 3: Core validation present; one guard missing where it would matter.
- 2: Several guards missing — output treated as one-shot, or gotchas buried mid-paragraph.
- 1: No verification anywhere and nothing prevents inappropriate attempts.

### 5. Context economy & delegation — smells UD, MUS

- 4: The body carries only what every run needs; low-level detail lives in references; script-worthy work is scripted; length well under the cap or the excess is justified.
- 3: Mostly lean; one block of reference-grade detail inline, or one obvious script left to improvisation.
- 2: Substantial inline detail that belongs in references or scripts; length near or past the cap without justification.
- 1: A dumping ground — every run pays for content few runs need.

### 6. Cold-reader comprehension — probe, no smell mapping

Fed by the D-010 probe. When only an estimate was possible, say so next to the score.

Fixed probe prompt — use it verbatim, never improvise questions (E-01: improvised questions made this the only dimension with score range 2 across identical runs). Pipe the target SKILL.md into the probe model with exactly this prompt:

> You are given one skill file for an AI agent, and nothing else. Answer from the file alone:
> 1. When should this skill be used, and when should it not be used?
> 2. List the steps or obligations the file imposes on the agent using it, in the file's order if it has one.
> 3. What must the agent never do while using this skill?
> 4. What artifacts must the agent produce, and in what format?
> 5. What does the file tell the agent to do when something is uncertain, missing, or goes wrong?
>
> If the file does not specify an item, answer "not specified" — do not fill gaps with conventional best practice.

You score the probe's answers against the file — the probe never scores itself. A misread is material when acting on it would change behavior on a task the description claims to handle; an answer the file supports but words differently is not a misread. Quote the probe's own words in each misread bullet.

- 4: The cold reader restates the skill's obligations correctly; no material misread.
- 3: Minor misreads that would not change behavior on target tasks.
- 2: One behavior-changing misread.
- 1: Multiple behavior-changing misreads, or the reader cannot say what the skill obliges.

## Smell definitions

Check each smell against its definition. "Counts" and "doesn't count" cues keep findings honest.

### Trigger & description

- CSD Confusing Skill Description — description lacks one of: what the skill does, when to use it, trigger keywords. Counts: a what-only description with no when-clause. Doesn't count: terse but complete; a skill with model invocation disabled needs the when-clause for humans, not routers — say so if it matters.
- USN Unclear Skill Name — name doesn't convey capability or action. Counts: codenames, puns. Doesn't count: short verb-object names.
- NTPD Non Third Person Description — frontmatter description in first or second person ("I help you…", "Use me when…"). Counts: I, me, my, we, our anywhere in the description; "you" addressed as the helped party ("helps you…", "lets you…"). Doesn't count: imperative mood, even in the description ("Use when asked to…") — accepted by convention despite its implied you; "your X" naming the object of the work ("reviews your code"); anything in the body — this smell is about the description field only.
- MUR Missing Usage Rules — behavior depends on situation but no rule says when or how the skill applies. Counts: multiple modes, no rule for choosing. Doesn't count: single-purpose skills whose when-clause is the only rule needed.

### Instruction quality

- TSW Stepless Workflow — a multi-step job written as one prose block. Counts: a paragraph interleaving three sequential actions. Doesn't count: genuinely single-action guidance.
- SOC Series of Commands — rigid line-by-line commands with hardcoded paths or arguments standing in for the objective. Counts: a copy-paste transcript with absolute paths. Doesn't count: one command clearly marked as an example.
- TOB Option Buffet — several tools or approaches offered, none recommended. Counts: "you can use A, B, or C". Doesn't count: options with a stated default and when to deviate.
- MDT Missing Decision Tree — a real fork in the work with no guidance for choosing by situation. Doesn't count: linear tasks with no fork.
- MT Missing Template — output must follow a format but no template or skeleton is given. Counts: the format spec being absent entirely — an absent spec is MT, not ME. Doesn't count: genuinely free-form outputs.

### Grounding & examples

- ME Missing Example — an example would change behavior, and there is none — or only a placeholder ("<YOUR_CODE_HERE>", lorem ipsum), which counts as missing (C09). Doesn't count: sections where an example adds nothing. Boundary with MT (E-01 filed the same absent spec both ways): if the missing thing would specify the shape of an artifact the agent must produce — fields, order, format — file MT, not ME; file ME when the rule is stated and only an illustration of it is missing. An example that was the only place a format was shown counts as MT, and the fix names the lost example. Never file the same omission as both ME and MT.
- TSS Time Sensitive Skill — content that silently goes stale: undated "latest version", "currently", pinned prices. Doesn't count: dated statements carrying their retrieval date.

### Verification & safeguards

- NVS No Validation Step — output treated as one-shot; no check-verify-iterate loop.
- EWP Execute Without a Plan — a complex task starts executing with no planning stage.
- NAH Never Asks Human — no point where the agent should stop and ask on uncertainty or high stakes.
- RL Rationalization Loophole — required steps carry no guard against being reasoned away. Counts: mandatory steps with nothing discouraging skipping. The paper found this in 94% of files — expect it.
- NPT No Progress Tracking — a long multi-step workflow with no checklist, todo, or state mechanism.
- NG No Guardrails — nothing prevents inappropriate or impossible attempts (wrong inputs, out-of-scope asks).
- BG Buried Gotchas — a critical warning hidden mid-paragraph instead of surfaced with a header, bold, or top placement.
- MC Missing Caveats — known failure modes or limits omitted, or stated without a resolution.

### Context economy & delegation

- UD Undelegated Detail — low-level reference detail inline in the body instead of in references files. Counts: a long lookup table inline. Doesn't count: a two-line table the workflow needs every run.
- MUS Missing Utility Script — deterministic, script-worthy work left for the agent to improvise (counting, parsing, mechanical validation). Doesn't count: judgment work no script can do.
