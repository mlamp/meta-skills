# fixtures — SKILL.md eval corpus

Eval set for the reviewer skill. Two kinds:

- real/ — unmodified SKILL.md files from real projects. What the reviewer meets in the wild. Note origin and date for each.
- planted/ — files with deliberately inserted flaws. Each fixture has a matching `<name>.manifest.md` listing every planted flaw. Recall = planted flaws caught / planted flaws.

Rules:

- A fixture never changes after a recorded result references it. Fix by adding a new fixture.
- Manifests list flaws plainly: one line per flaw, where it sits, what a reviewer should say about it.
