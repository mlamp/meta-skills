#!/usr/bin/env python3
"""Serialize one agent-voice generation run into a ledger line.

The model authors the report; this script owns the record (D-015 pattern, D-021):
it validates the report, hashes the files the run wrote, generates run id and
date, serializes with a JSON encoder, and appends — or prints the line when the
working directory has no ledger/runs.jsonl.

Usage: finalize.py <report.md> <target-project-path>

Report format (all sections required unless marked optional):

    # Generation: <target path>

    Model: <model id>
    Effort: <effort>

    ## Files
    - <one per bullet: path relative to target, or absolute / ~-prefixed for user-level files>

    ## Choices
    - sections: <comma list, e.g. purpose, patterns, boundaries, examples>
    - activation: project | user | both | none
    - settings-routed: <comma list of settings keys, or none>
    - mirror: yes | no

    ## Probe
    Model: <model id, or the word estimated>
    Misreads-Fixed: <integer>

    ## Notes            (optional)
    <free text>
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

LEDGER = os.path.join("ledger", "runs.jsonl")


def die(msg):
    sys.exit(f"VALIDATION ERROR: {msg}")


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def section(text, name):
    m = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def field(block, key, where):
    m = re.search(rf"^{key}:\s*(.+)$", block, re.M)
    if not m:
        die(f"missing '{key}:' in {where}")
    return m.group(1).strip()


def bullet_map(block, where):
    out = {}
    for line in block.splitlines():
        m = re.match(r"^- ([a-z-]+):\s*(.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    if not out:
        die(f"no '- key: value' bullets in {where}")
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    report_path, target = sys.argv[1], sys.argv[2]
    target = os.path.abspath(target)
    if not os.path.isdir(target):
        die(f"target is not a directory: {target}")
    text = open(report_path, encoding="utf-8").read()

    m = re.search(r"^# Generation:\s*(.+)$", text, re.M)
    if not m:
        die("missing '# Generation: <target path>' title")
    head = text.split("## ", 1)[0]
    model = field(head, "Model", "header")
    effort = field(head, "Effort", "header")

    files_block = section(text, "Files") or die("missing '## Files'")
    rels = re.findall(r"^- (.+)$", files_block, re.M)
    if not rels:
        die("'## Files' lists no files")
    hashes = {}
    for rel in rels:
        p = os.path.expanduser(rel) if rel.startswith(("~", "/")) else os.path.join(target, rel)
        if not os.path.isfile(p):
            die(f"listed file not found: {rel}")
        hashes[rel] = sha16(p)

    choices = bullet_map(section(text, "Choices") or die("missing '## Choices'"), "Choices")
    for k in ("sections", "activation", "settings-routed", "mirror"):
        if k not in choices:
            die(f"missing '- {k}:' in Choices")
    if choices["activation"] not in ("project", "user", "both", "none"):
        die("activation must be project | user | both | none")
    if choices["mirror"] not in ("yes", "no"):
        die("mirror must be yes | no")

    probe_block = section(text, "Probe") or die("missing '## Probe'")
    probe_model = field(probe_block, "Model", "Probe")
    misreads = field(probe_block, "Misreads-Fixed", "Probe")
    if not misreads.isdigit():
        die("Misreads-Fixed must be an integer")

    notes = section(text, "Notes") or ""

    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        sha = subprocess.run(
            ["git", "-C", skill_dir, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", skill_dir, "status", "--porcelain", "."],
            capture_output=True, text=True, check=True).stdout.strip()
        version = sha + ("-dirty" if dirty else "")
    except Exception:
        version = "unknown"

    payload = {
        "schema_version": 2,
        "type": "generation",
        "target": {"path": target, "files_sha256_16": hashes},
        "generator": {"skill": "agent-voice", "version_sha": version,
                      "model": model, "effort": effort},
        "choices": choices,
        "probe": {"model": probe_model, "misreads_fixed": int(misreads)},
        "notes": notes,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
    now = datetime.now(timezone.utc)
    line_obj = {"schema_version": 2, "type": "generation",
                "run_id": f"r-{now:%Y%m%d}-{digest}",
                "date": now.isoformat(timespec="seconds"), **{
                    k: payload[k] for k in
                    ("target", "generator", "choices", "probe", "notes")}}
    line = json.dumps(line_obj, sort_keys=False)

    if os.path.isfile(LEDGER):
        with open(LEDGER, "rb") as f:
            data = f.read()
        if data and not data.endswith(b"\n"):
            die("ledger does not end in a newline; fix it first")
        if line_obj["run_id"].encode() in data:
            die(f"duplicate run_id {line_obj['run_id']} already in ledger")
        fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(fd, line.encode() + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        print(f"committed {line_obj['run_id']} to {LEDGER}")
    else:
        print("no ledger/runs.jsonl in the working directory; file this line:")
        print(line)

    print(f"\nGeneration recorded for {target}")
    for rel, h in hashes.items():
        print(f"  {rel}  {h}")


if __name__ == "__main__":
    main()
