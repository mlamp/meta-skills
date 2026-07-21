# frontend-design-p1 — flaw manifest

Derived from fixtures/real/frontend-design/2026-06-09-2235be7 (anthropics/skills, Apache-2.0 — LICENSE.txt rides in the fixture dir). Planted 2026-07-21 for review-skill evals. All flaws live in SKILL.md. Never shown to the reviewer during a run (D-013).

Off-manifest findings are adjudicated by the user, not auto-counted as false positives (C02). Recall = planted caught / 12. Five flaws are deletions — they test sensitivity to absences and are expected to be the hard half.

Planted flaws, one per line:

1. NTPD — frontmatter description — "Use me when you want your UI…": second person; original was third person.
2. LSD — frontmatter description — 1,045 chars of keyword stuffing (cap 1,024).
3. NAH — "Ground it in the subject", last sentence — "Never ask the user clarifying questions about the brief; make every decision yourself." Forbids human escalation outright.
4. MDT — Design principles — "Decide early whether the page should be single-page or multi-section with navigation." A real fork, zero criteria for choosing.
5. ME (deletion) — Process, calibration line — the original's three concrete cliché looks (cream + serif + terracotta; near-black + acid accent; broadsheet hairlines) replaced by "avoid designs that look obviously AI-generated or generic." The behavior-anchoring examples are gone; vague advice remains.
6. MUR (deletion) — same region — the original rule "where the brief pins down a visual direction, follow it exactly — the brief's own words always win" is gone; no rule left for brief-vs-distinctiveness conflicts.
7. MT (deletion) — Process, token system — the original's concrete spec (4–6 named hex values; 2+ type roles; ASCII wireframes; signature element definition) reduced to "covering color, type, layout, and a signature element." Output needs a format; no template given. Also the dimension-6 bait: a cold reader asked "what must the design plan contain?" cannot answer precisely.
8. REF — Process — "Record your token system in references/tokens.md": file doesn't exist in the fixture.
9. BP — Process — `assets\wireframes\`: backslash path.
10. EWP (deletion) — Process — the original's review-plan-against-brief pass ("Only after you've confirmed… should you start to write the code") removed; the text now goes straight from brainstorm to build.
11. MC (deletion) — the original's CSS selector-specificity caveat paragraph (classes canceling out, section padding/margin conflicts) removed entirely; a known failure mode with its resolution is gone.
12. MUS — Restraint and self-critique, last sentence — "read through the final CSS top to bottom and hand-count every pair of selectors whose specificity conflicts": deterministic, script-worthy work assigned to the agent by hand.
