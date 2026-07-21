# Kickoff — design session for skill #1 (the SKILL.md reviewer)

Working name until the session picks one. Paste the prompt below into a fresh session in this repo.

---

We're designing skill #1 of this repo: a skill that takes a SKILL.md (or a whole skill directory) and reviews it — findings, rubric scores, concrete fixes.

Read first, in order: CLAUDE.md, DECISIONS.md, research/CLAIMS.md, then skim research/notes/. Everything in research/ is unproven input: use it for ideas. Anything we adopt becomes a design assumption tied to a claim number with a validation plan — not a fact.

Work through these in order. Every weight-bearing fork goes through AskUserQuestion with options and a recommendation — and proactively suggest valuable ideas of your own the same way.

1. Job definition. Exact inputs (single SKILL.md? full skill dir with scripts and references? usage transcripts?), outputs (findings list, rubric scores, suggested rewrite or patch?), and explicit non-goals.
2. Name. Short, verb-first, unambiguous. Its own description must follow [what it does] + [when to use it] + [keywords] (C04).
3. Rubric v0. Dimensions with per-level anchors. Seed candidates: the 26-smell catalog (C01, notes/2607.01456), instruction clarity and length (C08), example quality — real, not placeholder (C09), trigger/description quality (C04, C12), cold-reader comprehension. Keep mechanical checks (grep/script) separate from judgment checks (LLM judge), per the static/semantic split in notes/2607.01456.
4. Measurement plan. fixtures/: pick 2–3 real SKILL.md files with the user as first subjects; design the first planted-defect fixtures and their flaw manifests; define recall/precision on planted flaws; repeated runs with variance, never single runs (C10, C11); a second model family for scores that matter. Define the ledger here: fields, location, format — D-006 left this to this session.
5. Draft skills/<name>/SKILL.md, status: draft. It must pass its own review (self-application) and a cold-reader probe before it lands.
6. Close out: DECISIONS entries for every call made; CLAIMS.md updated (new claims adopted, statuses to move); the validation experiments queued next.

Session rules: plain english, no prose, no contradictions. Decisions land in DECISIONS.md the moment they're made, not at the end.
