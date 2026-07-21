# provenance — grill-with-docs

- Source: https://github.com/mattpocock/skills · path `skills/engineering/grill-with-docs` · MIT (copy: ../LICENSE-mattpocock-skills.txt)
- Why taken: user-named popular skill; its history shows a full shape inversion worth comparing.
- Path history: 12 commits, 2026-04-28 → 2026-07-13. Retrieved 2026-07-21.

Snapshots — dir is `<commit-date>-<sha7>`; content is the path at that commit, unmodified:

- 2026-04-30-b843cb5 · b843cb5ea74b1fe5e58a0fc23cddef9e66076fb8 · "Add structured sections for 'what-to-do' and 'supporting-info' in SKILL.md"
  Files: SKILL.md (3.5k), ADR-FORMAT.md, CONTEXT-FORMAT.md. Self-contained: instructions plus two format reference docs.
- 2026-07-13-697d4ce · 697d4ce9742da558fd1ba6697c8e9775e2e302dd · "feat: add Codex agents/openai.yaml metadata to every skill"
  Files: SKILL.md (245 bytes), agents/openai.yaml. Now a 7-line alias: frontmatter plus one line delegating to /grilling and /domain-modeling. `disable-model-invocation: true` is back after being removed 2026-04-30.

Not vendored: the sibling skills the current version delegates to — `skills/productivity/grilling` and `skills/engineering/domain-modeling` at the same commit. Re-fetch them if an eval needs them.

Re-fetch any file: `curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/<full-sha>/<path>`
