# skill-creator-p1 — planted-flaw manifest (answer key)

Base: fixtures/real/skill-creator/2026-02-06-1ed29a0 (Apache-2.0), copied unmodified, then 12 flaws planted for E-06. Deletion-heavy per the E-06 kickoff: 8 pure deletions of real guidance, at least 6 leaving no vague residue. Never show this file or the spans TSV to a reviewer (D-013); machine spans in skill-creator-p1.spans.tsv.

Flaws:

1. CSD · SKILL.md:1-4 · deletion, no residue — the description's when-to-use sentence ("This skill should be used when users want to create a new skill (or update an existing skill)…") deleted; only "Guide for creating effective skills." remains. A reviewer should say: what-only description, no when-clause, no trigger keywords.
2. MDT · SKILL.md:34-41 · deletion (labels reformatted, so not byte-pure) — the three "Use when…" selection cues and the bridge/cliff analogy deleted from Set Appropriate Degrees of Freedom; the three freedom levels remain with no rule for choosing between them. A reviewer should say: a real fork with no situational guidance.
3. TSS · SKILL.md:248-256 · insertion — "The script tracks the latest revision of the skill format, and skills initialized with it are accepted by all current Claude releases." added to Step 3; undated latest/current claim that silently goes stale.
4. ME · SKILL.md:294-303 · deletion, no residue — the docx example description bullet deleted from the Frontmatter guidance; the rule ("Include both what the Skill does and specific triggers/contexts") stays, its only illustration is gone. Per the rubric boundary this is ME (rule stated, illustration missing), not MT.
5. RL · SKILL.md:197-207 · deletion, no residue — "Follow these steps in order, skipping only if there is a clear reason why they are not applicable." deleted after the six-step process list; the required sequence now carries no guard against steps being reasoned away.
6. NVS · SKILL.md:284-289 · deletion, no residue — the paragraph "Added scripts must be tested by actually running them… balancing time to completion." deleted; scripts are now added with no run-and-verify loop anywhere.
7. MC · SKILL.md:69-76 · deletion, no residue — the Note that scripts may still need to be read by Claude for patching or environment-specific adjustments deleted; the scripts-are-token-efficient benefits now carry no caveat about when that fails.
8. MUS · SKILL.md:197-206 · deletion, no residue — the whole "Step 5: Packaging a Skill" section and its process-list line deleted; Iterate renumbered 6→5 and one "or packaging" mention trimmed from Step 3's skip rule. scripts/package_skill.py still ships in the directory, unreferenced by the body; producing the distributable is left to improvisation. Reviewers may instead cite scripts/package_skill.py itself or the Step 4→5 boundary — credit those as flaw:8.
9. BP · SKILL.md:259 · insertion · static BP — the Step 3 usage command reads scripts\init_skill.py (backslash path). It is a real command the agent runs, not an illustration, so a Static override here would be wrong.
10. FM-parse · SKILL.md:1-4 · deletion · static FM-parse — the "name: skill-creator" frontmatter line deleted.
11. UD · SKILL.md:304-320 · insertion — a 13-row frontmatter validation-rules lookup table inlined into the body (content invented for the plant); reference-grade detail that belongs in a references/ file.
12. MT · references/output-patterns.md:1-35 · deletion, no residue in-file — the entire "Template Pattern" section (both strict and flexible template blocks) deleted; the file now holds only the Examples Pattern while SKILL.md:280 still promises "template and example patterns". Per the rubric boundary an absent shape spec is MT. Reviewers citing the SKILL.md:280 pointer get flaw:12 credit.

Coverage: dimension 1 (CSD), dimension 2 (MDT, MT), dimension 3 (TSS, ME), dimension 4 (RL, NVS, MC), dimension 5 (MUS, UD), static (BP, FM-parse). Pure deletions: flaws 1, 4, 5, 6, 7, 8, 10, 12.

Pre-existing, not planted: REF fails on the unmodified base — 17 illustrative example paths (references/finance.md, assets/logo.png, DOCX-JS.md, …) that never existed upstream. Expected reviewer behavior is a Static override with an illustrative-paths reason; adjudicate REF-related findings as pre-existing either way. Other off-manifest findings are adjudicated per D-013, never auto-counted as false positives.
