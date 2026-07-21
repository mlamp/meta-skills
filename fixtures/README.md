# fixtures — SKILL.md eval corpus

Eval set for the reviewer skill. Two kinds:

- real/ — skills vendored from real projects, unmodified, pinned to an upstream commit. What the reviewer meets in the wild.
- planted/ — files with deliberately inserted flaws. Each fixture has a matching `<name>.manifest.md` listing every planted flaw. Recall = planted flaws caught / planted flaws.

Layout of real/:

- real/<name>/<commit-date>-<sha7>/ — one snapshot: the skill's files at that upstream commit, unmodified.
- real/<name>/PROVENANCE.md — source repo, path, license, each snapshot's full SHA, re-fetch command, retrieval date.
- When upstream history moved, take a pair (oldest useful + current) so review output can be compared across versions.
- Third-party licenses: when upstream ships a per-skill license, it rides inside each snapshot; otherwise a repo-level copy lands at real/LICENSE-<source>.txt. A source with no license gets a warning in its PROVENANCE and must be resolved before this repo goes public.

Rules:

- A real/ snapshot never changes, period — it is a pinned upstream state. New upstream state → new snapshot dir.
- A planted/ fixture never changes after a recorded result references it. Fix by adding a new fixture.
- Manifests list flaws plainly: one line per flaw, where it sits, what a reviewer should say about it.
