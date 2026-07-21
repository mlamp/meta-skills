#!/usr/bin/env python3
"""Layer-1 static checks for review-skill.

Usage: static_checks.py <path-to-skill-dir-or-SKILL.md>
Prints one JSON object: {"target", "mode", "checks": {id: {"status", "evidence"}}}.
Statuses: pass | fail | skipped. Deterministic; no LLM judgment here.
"""
import json
import re
import sys
from pathlib import Path

WORD_CAP = 5000   # LSB — threshold from C05, untested; see references/rubric.md
NAME_CAP = 64     # LSN
DESC_CAP = 1024   # LSD


def parse_frontmatter(text):
    """Naive YAML subset: top-level 'key: value' pairs, folded/literal blocks,
    and indented plain-scalar continuations. Returns (dict | None, body, body_offset)
    where body_offset is the number of file lines before the body, so evidence
    can cite file line numbers."""
    if not text.startswith("---"):
        return None, text, 0
    lines = text.split("\n")
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None, text, 0
    fm, body = {}, "\n".join(lines[end + 1:])
    key = None
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            fm[key] = "" if val in (">", ">-", "|", "|-") else val
        elif key and line.startswith((" ", "\t")) and line.strip():
            fm[key] = (fm[key] + " " + line.strip()).strip()
    return fm, body, end + 1


def find_backslash_paths(body, offset=0):
    """Line numbers in hits are file line numbers: body line + offset."""
    hits = []
    patterns = [
        r"[A-Za-z]:\\[^\s`\"']+",                              # drive letter
        r"\.\.?\\[A-Za-z0-9_.-]+",                             # dot-relative
        r"(?:[A-Za-z0-9_.-]+\\){2,}[A-Za-z0-9_.-]+",           # two+ separators
        r"(?:[A-Za-z0-9_.-]{2,}\\){2,}(?=\s|$)",               # dir path, trailing backslash
        r"[A-Za-z0-9_-]{2,}\\[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,4}\b",  # seg\file.ext
    ]
    for n, line in enumerate(body.split("\n"), start=1 + offset):
        for p in patterns:
            for m in re.finditer(p, line):
                hits.append(f"line {n}: {m.group(0)}")
    return sorted(set(hits))


def find_missing_refs(body, skill_dir):
    """Relative file references in the body that don't exist on disk."""
    tokens = set()
    for m in re.finditer(r"\]\(([^)#\s]+)\)", body):          # markdown links
        tokens.add(m.group(1))
    for m in re.finditer(r"(?<![\w/])((?:references|scripts|assets)/[A-Za-z0-9_./-]+)", body):
        tokens.add(m.group(1))
    missing = []
    for t in sorted(tokens):
        if re.match(r"^[a-z]+://", t) or t.startswith("mailto:"):
            continue
        rel = t.strip("`\"'").rstrip(".,;:")
        if not rel or rel.startswith("/"):
            continue
        if not (skill_dir / rel).exists():
            missing.append(rel)
    return missing


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: static_checks.py <skill-dir-or-SKILL.md>"}))
        sys.exit(2)
    target = Path(sys.argv[1])
    if target.is_dir():
        mode, skill_md, skill_dir = "dir", target / "SKILL.md", target
    else:
        mode, skill_md, skill_dir = "file", target, None
    if not skill_md.is_file():
        print(json.dumps({"error": f"no SKILL.md at {skill_md}"}))
        sys.exit(2)

    text = skill_md.read_text(encoding="utf-8")
    fm, body, body_offset = parse_frontmatter(text)
    checks = {}

    def result(cid, ok, evidence):
        checks[cid] = {"status": "pass" if ok else "fail", "evidence": evidence}

    if fm is None:
        result("FM-parse", False, ["no parseable frontmatter block"])
        name, desc = None, None
    else:
        name, desc = fm.get("name"), fm.get("description")
        missing = [k for k in ("name", "description") if not fm.get(k)]
        result("FM-parse", not missing,
               [f"missing frontmatter key: {k}" for k in missing])

    if name is not None:
        result("LSN", len(name) <= NAME_CAP, [f"name is {len(name)} chars (cap {NAME_CAP})"] if len(name) > NAME_CAP else [])
    else:
        checks["LSN"] = {"status": "skipped", "evidence": ["no name to check"]}

    if desc is not None:
        result("LSD", len(desc) <= DESC_CAP, [f"description is {len(desc)} chars (cap {DESC_CAP})"] if len(desc) > DESC_CAP else [])
        tags = re.findall(r"<[A-Za-z/][^>]*>", desc)
        result("XID", not tags, [f"tag in description: {t}" for t in tags])
    else:
        checks["LSD"] = {"status": "skipped", "evidence": ["no description to check"]}
        checks["XID"] = {"status": "skipped", "evidence": ["no description to check"]}

    words = len(body.split())
    result("LSB", words <= WORD_CAP, [f"body is {words} words (cap {WORD_CAP})"] if words > WORD_CAP else [])
    checks["LSB"]["evidence"].insert(0, f"body word count: {words}")

    bp = find_backslash_paths(body, body_offset)
    result("BP", not bp, bp)

    if mode == "dir":
        missing = find_missing_refs(body, skill_dir)
        result("REF", not missing, [f"referenced but missing: {m}" for m in missing])
    else:
        checks["REF"] = {"status": "skipped", "evidence": ["lone SKILL.md — cannot check referenced files"]}

    print(json.dumps({"target": str(target), "mode": mode, "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
