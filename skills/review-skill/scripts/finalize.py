#!/usr/bin/env python3
"""review-skill finalizer: parses the model-authored report, validates it,
extracts evidence from cited spans, and commits one ledger line (D-015).

The model never writes JSON, run IDs, dates, or SHAs. This script does.

Usage:
  finalize.py <report.md> <target-path> [--ledger FILE | --outbox DIR | --print]
              [--batch-id ID] [--batch-seq N] [--repo DIR]
  finalize.py --drain DIR --ledger FILE

Default sink: ledger/runs.jsonl under the current directory if present,
else --print behavior (canonical report + ledger line to stdout).
Exit codes: 0 committed/printed, 1 validation error (fix the report, rerun), 2 usage.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 2
SCRIPT_DIR = Path(__file__).resolve().parent

SEMANTIC_SMELLS = {
    "CSD", "USN", "NTPD", "MUR",          # trigger & description
    "TSW", "SOC", "TOB", "MDT", "MT",     # instruction quality
    "ME", "TSS",                          # grounding & examples
    "NVS", "EWP", "NAH", "RL", "NPT", "NG", "BG", "MC",  # verification & safeguards
    "UD", "MUS",                          # context economy & delegation
}
STATIC_CHECKS = {"FM-parse", "LSN", "LSD", "XID", "LSB", "BP", "REF"}
VALID_SMELLS = SEMANTIC_SMELLS | STATIC_CHECKS

SCORE_KEYS = ["Trigger", "Instructions", "Grounding", "Verification", "Economy", "Cold-Reader"]
HEADER_KEYS = {"Reviewer-Model", "Reviewer-Effort", "Repeats-In-Batch", "Probe-Model", "Omitted-Findings"}
REQUIRED_HEADERS = {"Reviewer-Model", "Repeats-In-Batch", "Probe-Model"}
SECTIONS = ["Findings", "Scores", "Probe-Misreads", "Static overrides", "Notes"]
REQUIRED_SECTIONS = {"Findings", "Scores", "Probe-Misreads"}
FINDING_KEYS = {"File", "Lines", "Anchor", "Why", "Fix", "Uncertain"}
REQUIRED_FINDING_KEYS = {"File", "Lines", "Anchor", "Why", "Fix"}
MAX_SPAN_LINES = 40

STATIC_FIX_HINTS = {
    "FM-parse": "make the frontmatter parse with name and description present",
    "LSN": "shorten the name to 64 characters or fewer",
    "LSD": "shorten the description to 1,024 characters or fewer",
    "XID": "remove XML/HTML tags from the description",
    "LSB": "move detail into references/ files loaded on demand (threshold from C05, untested)",
    "BP": "use forward slashes in paths",
    "REF": "fix or remove references to files that do not exist",
}


class Fail(Exception):
    pass


def die(msg):
    raise Fail(msg)


# ---------- report parsing (total parse: everything must be consumed) ----------

def parse_report(text):
    lines = text.split("\n")
    i = 0
    rep = {"headers": {}, "findings": [], "scores": {}, "misreads": [],
           "overrides": {}, "notes": ""}

    def skip_blank():
        nonlocal i
        while i < len(lines) and not lines[i].strip():
            i += 1

    skip_blank()
    if i >= len(lines) or not lines[i].startswith("# Review:"):
        die(f"line {i+1}: report must start with '# Review: <name> (<path>)'")
    i += 1
    skip_blank()

    while i < len(lines) and re.match(r"^[A-Za-z-]+:", lines[i]):
        key, _, val = lines[i].partition(":")
        key = key.strip()
        if key not in HEADER_KEYS:
            die(f"line {i+1}: unknown header '{key}' (allowed: {sorted(HEADER_KEYS)})")
        if key in rep["headers"]:
            die(f"line {i+1}: duplicate header '{key}'")
        rep["headers"][key] = val.strip()
        i += 1

    missing = REQUIRED_HEADERS - rep["headers"].keys()
    if missing:
        die(f"missing required header(s): {sorted(missing)}")

    seen_sections = []
    cur = None
    finding = None
    field = None

    def close_finding():
        nonlocal finding, field
        if finding is not None:
            miss = REQUIRED_FINDING_KEYS - finding["fields"].keys()
            if miss:
                die(f"finding {finding['id']}: missing field(s) {sorted(miss)}")
            rep["findings"].append(finding)
        finding, field = None, None

    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            close_finding()
            cur = line[3:].strip()
            if cur not in SECTIONS:
                die(f"line {i+1}: unknown section '## {cur}' (allowed: {SECTIONS})")
            if cur in seen_sections:
                die(f"line {i+1}: duplicate section '## {cur}'")
            seen_sections.append(cur)
            i += 1
            continue
        if cur == "Findings":
            m = re.match(r"^### (F\d+) · ([A-Za-z-]+)( · blocker)?\s*$", line)
            if m:
                close_finding()
                fid, smell, blocker = m.group(1), m.group(2), bool(m.group(3))
                if any(f["id"] == fid for f in rep["findings"]):
                    die(f"line {i+1}: duplicate finding id {fid}")
                if smell not in VALID_SMELLS:
                    die(f"line {i+1}: unknown smell ID '{smell}' (see references/rubric.md)")
                finding = {"id": fid, "smell_id": smell, "blocker": blocker, "fields": {}}
                field = None
            elif finding is not None:
                fm = re.match(r"^([A-Za-z]+):\s?(.*)$", line)
                if fm and fm.group(1) in FINDING_KEYS:
                    key = fm.group(1)
                    if key in finding["fields"]:
                        die(f"line {i+1}: duplicate field '{key}' in finding {finding['id']}")
                    finding["fields"][key] = fm.group(2)
                    field = key
                elif field in ("Why", "Fix") and (line.strip() or field):
                    if line.startswith("### "):
                        die(f"line {i+1}: malformed finding header")
                    finding["fields"][field] += "\n" + line
                elif line.strip():
                    die(f"line {i+1}: unexpected content in finding {finding['id']}: {line!r}")
            elif line.strip():
                die(f"line {i+1}: content in Findings outside a '### Fn · SMELL' block: {line!r}")
        elif cur == "Scores":
            if line.strip():
                sm = re.match(r"^([A-Za-z-]+):\s*([0-9.]+)\s*$", line)
                if not sm or sm.group(1) not in SCORE_KEYS:
                    die(f"line {i+1}: Scores lines must be exactly '<{'|'.join(SCORE_KEYS)}>: <1-4>', got: {line!r}")
                if sm.group(1) in rep["scores"]:
                    die(f"line {i+1}: duplicate score '{sm.group(1)}'")
                if not re.match(r"^[1-4]$", sm.group(2)):
                    die(f"line {i+1}: score must be an integer 1-4, got '{sm.group(2)}'")
                rep["scores"][sm.group(1)] = int(sm.group(2))
        elif cur == "Probe-Misreads":
            if line.strip():
                if line.strip().lower() == "none":
                    pass
                elif line.startswith("- "):
                    rep["misreads"].append(line[2:].strip())
                else:
                    die(f"line {i+1}: Probe-Misreads entries must be '- <text>' bullets or 'none'")
        elif cur == "Static overrides":
            if line.strip():
                om = re.match(r"^- ([A-Za-z-]+): drop — (.+)$", line)
                if not om:
                    die(f"line {i+1}: overrides must be '- <CHECK>: drop — <reason>', got: {line!r}")
                if om.group(1) not in STATIC_CHECKS:
                    die(f"line {i+1}: unknown static check '{om.group(1)}'")
                rep["overrides"][om.group(1)] = om.group(2).strip()
        elif cur == "Notes":
            rep["notes"] += line + "\n"
        elif line.strip():
            die(f"line {i+1}: content before any section: {line!r}")
        i += 1

    close_finding()
    missing = REQUIRED_SECTIONS - set(seen_sections)
    if missing:
        die(f"missing required section(s): {sorted('## ' + s for s in missing)}")
    missing_scores = [k for k in SCORE_KEYS if k not in rep["scores"]]
    if missing_scores:
        die(f"Scores section missing: {missing_scores}")
    if not re.match(r"^\d+$", rep["headers"]["Repeats-In-Batch"]):
        die("Repeats-In-Batch must be an integer")
    om = rep["headers"].get("Omitted-Findings", "0")
    if not re.match(r"^\d+$", om):
        die("Omitted-Findings must be an integer")
    rep["notes"] = rep["notes"].strip()
    return rep


# ---------- evidence extraction ----------

def norm_ws(s):
    return " ".join(s.split())


def extract_evidence(finding, target_dir, single_file):
    f = finding["fields"]
    rel = f["File"].strip()
    if single_file is not None:
        path = single_file if rel in (single_file.name, str(single_file)) else None
        if path is None:
            die(f"finding {finding['id']}: File must be '{single_file.name}' when reviewing a lone file")
    else:
        path = (target_dir / rel).resolve()
        if not str(path).startswith(str(target_dir.resolve()) + os.sep):
            die(f"finding {finding['id']}: File '{rel}' escapes the target directory")
        if not path.is_file():
            die(f"finding {finding['id']}: File '{rel}' does not exist in the target")
    lm = re.match(r"^(\d+)(?:-(\d+))?$", f["Lines"].strip())
    if not lm:
        die(f"finding {finding['id']}: Lines must be 'N' or 'N-M', got '{f['Lines']}'")
    start, end = int(lm.group(1)), int(lm.group(2) or lm.group(1))
    if end < start:
        die(f"finding {finding['id']}: Lines range end before start")
    if end - start + 1 > MAX_SPAN_LINES:
        die(f"finding {finding['id']}: span is {end-start+1} lines; cap is {MAX_SPAN_LINES} — cite the load-bearing lines")
    file_lines = path.read_text(encoding="utf-8").split("\n")
    if end > len(file_lines):
        die(f"finding {finding['id']}: Lines {start}-{end} but {rel} has {len(file_lines)} lines")
    evidence = "\n".join(file_lines[start - 1:end])
    anchor = f["Anchor"].strip()
    if not anchor:
        die(f"finding {finding['id']}: Anchor must not be empty")
    if norm_ws(anchor) not in norm_ws(evidence):
        ctx_start = max(0, start - 4)
        ctx = "\n".join(f"  {n+1}: {file_lines[n]}" for n in range(ctx_start, min(len(file_lines), end + 3)))
        die(f"finding {finding['id']}: anchor {anchor!r} not found in {rel}:{start}-{end}.\n"
            f"Span and surroundings:\n{ctx}\nFix Lines or Anchor to match the file.")
    return {"file": rel, "lines": f"{start}-{end}", "evidence": evidence}


# ---------- machine facts ----------

def run_static_checks(target):
    out = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "static_checks.py"), str(target)],
        capture_output=True, text=True)
    if out.returncode not in (0,):
        die(f"static_checks.py failed: {out.stdout} {out.stderr}")
    return json.loads(out.stdout)["checks"]


def reviewer_sha():
    try:
        sha = subprocess.run(["git", "-C", str(SCRIPT_DIR), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(SCRIPT_DIR), "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def target_shas(target_dir, single_file, cited_files):
    files = {}
    paths = [single_file] if single_file else sorted(
        {target_dir / "SKILL.md", *[target_dir / c for c in cited_files]})
    for p in paths:
        if p and p.is_file():
            files[p.name if single_file else str(p.relative_to(target_dir))] = \
                hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return files


# ---------- record assembly ----------

def build_record(rep, target, args):
    target = Path(target)
    single_file = target if target.is_file() else None
    target_dir = target if target.is_dir() else target.parent

    findings = []
    for fnd in rep["findings"]:
        ev = extract_evidence(fnd, target_dir, single_file)
        entry = {"smell_id": fnd["smell_id"], "location": f"{ev['file']}:{ev['lines']}",
                 "evidence": ev["evidence"], "blocker": fnd["blocker"],
                 "why": norm_ws(fnd["fields"]["Why"]), "fix": norm_ws(fnd["fields"]["Fix"])}
        if fnd["fields"].get("Uncertain", "").strip().lower() in ("yes", "true"):
            entry["uncertain"] = True
        findings.append(entry)

    static = run_static_checks(target)
    for check, res in static.items():
        if check in rep["overrides"]:
            if res["status"] != "fail":
                die(f"Static overrides: '{check}' is '{res['status']}', not 'fail' — nothing to drop")
            res["override"] = "dropped"
            res["reason"] = rep["overrides"][check]
        elif res["status"] == "fail":
            findings.append({
                "smell_id": check, "location": "static",
                "evidence": "; ".join(res["evidence"]), "blocker": False,
                "why": "static check failed", "fix": STATIC_FIX_HINTS[check]})

    probe_val = rep["headers"]["Probe-Model"].strip()
    probe = {"estimated": True} if probe_val.lower() == "estimated" \
        else {"model": probe_val, "misreads": rep["misreads"]}
    if probe_val.lower() == "estimated" and rep["misreads"]:
        die("Probe-Misreads must be 'none' when Probe-Model is 'estimated'")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": "review",
        "target": {"path": str(target),
                   "files_sha256_16": target_shas(target_dir, single_file,
                                                  [f["location"].split(":")[0] for f in findings
                                                   if f["location"] != "static"])},
        "reviewer": {"skill": "review-skill", "version_sha": reviewer_sha(),
                     "model": rep["headers"]["Reviewer-Model"],
                     "effort": rep["headers"].get("Reviewer-Effort")},
        "repeats_in_batch": int(rep["headers"]["Repeats-In-Batch"]),
        "omitted_findings": int(rep["headers"].get("Omitted-Findings", "0")),
        "static": static,
        "findings": findings,
        "scores": {k.lower().replace("-", "_"): v for k, v in rep["scores"].items()},
        "probe": probe,
        "vs_manifest": None,
        "notes": rep["notes"],
    }
    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    day = now.strftime("%Y%m%d")
    batch_id = args.batch_id or f"b-{day}-solo"
    content_hash = hashlib.sha256(
        json.dumps([payload, batch_id, args.batch_seq], sort_keys=True).encode()).hexdigest()[:10]
    payload["run_id"] = f"r-{day}-{content_hash}"
    payload["batch_id"] = batch_id
    payload["batch_seq"] = args.batch_seq
    payload["date"] = now.isoformat(timespec="seconds")
    return payload


# ---------- rendering ----------

def render(payload):
    out = [f"# Review: {payload['target']['path']}", ""]
    blockers = [f for f in payload["findings"] if f["blocker"]]
    out.append("## Blockers")
    out += [f"- {f['smell_id']} at {f['location']}: {f['why']}" for f in blockers] or ["none"]
    out.append("\n## Findings")
    for f in payload["findings"]:
        tag = " · blocker" if f["blocker"] else ""
        tag += " · uncertain" if f.get("uncertain") else ""
        quote = f["evidence"] if len(f["evidence"]) <= 300 else f["evidence"][:300] + "…"
        out.append(f"- {f['smell_id']} at {f['location']}{tag}: {quote!r} — {f['why']} Fix: {f['fix']}")
    if not payload["findings"]:
        out.append("none")
    sc = payload["scores"]
    est = " (estimated)" if payload["probe"].get("estimated") else ""
    out.append(f"\n## Scores\ntrigger {sc['trigger']} · instructions {sc['instructions']} · "
               f"grounding {sc['grounding']} · verification {sc['verification']} · "
               f"economy {sc['economy']} · cold-reader {sc['cold_reader']}{est}")
    skipped = [f"{k}: {'; '.join(v['evidence'])}" for k, v in payload["static"].items()
               if v["status"] == "skipped"]
    dropped = [f"{k} dropped — {v['reason']}" for k, v in payload["static"].items()
               if v.get("override")]
    out.append("\n## Skipped / overridden")
    out += [f"- {s}" for s in skipped + dropped] or ["none"]
    if payload["omitted_findings"]:
        out.append(f"\nOMITTED FINDINGS: {payload['omitted_findings']} (review hit an output cap)")
    out.append(f"\nrun {payload['run_id']} · batch {payload['batch_id']} seq {payload['batch_seq']}"
               f" · reviewer {payload['reviewer']['version_sha']}")
    return "\n".join(out)


# ---------- commit ----------

def append_line(ledger, payload):
    line = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if ledger.exists() and ledger.stat().st_size:
        with open(ledger, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                die(f"{ledger} does not end with a newline — last line is partial; resolve by hand before appending")
        for existing in ledger.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(existing).get("run_id") == payload["run_id"]:
                    return False
            except json.JSONDecodeError:
                die(f"{ledger} contains an unparseable line — resolve by hand before appending")
    fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def write_outbox(outbox, payload):
    outbox.mkdir(parents=True, exist_ok=True)
    final = outbox / f"{payload['run_id']}.json"
    tmp = outbox / f".{payload['run_id']}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(tmp, final)
    return final


def drain(outbox, ledger):
    committed_dir = outbox / "committed"
    committed_dir.mkdir(exist_ok=True)
    n = 0
    for f in sorted(outbox.glob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"QUARANTINED (unparseable, left in place): {f}", file=sys.stderr)
            continue
        for key in ("run_id", "schema_version", "findings", "scores", "static"):
            if key not in payload:
                die(f"{f}: missing '{key}' — not a valid outbox record")
        if append_line(ledger, payload):
            n += 1
        os.replace(f, committed_dir / f.name)
    print(f"drained {n} new line(s) into {ledger}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", nargs="?")
    ap.add_argument("target", nargs="?")
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--outbox", type=Path)
    ap.add_argument("--print", dest="print_only", action="store_true")
    ap.add_argument("--drain", type=Path)
    ap.add_argument("--batch-id")
    ap.add_argument("--batch-seq", type=int, default=1)
    args = ap.parse_args()

    try:
        if args.drain:
            if not args.ledger:
                die("--drain requires --ledger")
            drain(args.drain, args.ledger)
            return
        if not args.report or not args.target:
            ap.error("report and target are required (or use --drain)")
        rep = parse_report(Path(args.report).read_text(encoding="utf-8"))
        payload = build_record(rep, args.target, args)
        print(render(payload))
        if args.outbox:
            print(f"\nOUTBOX: {write_outbox(args.outbox, payload)}")
        elif args.print_only:
            print("\n## Ledger line (no ledger found — file this)\n" + json.dumps(payload, ensure_ascii=False))
        else:
            ledger = args.ledger or Path("ledger/runs.jsonl")
            if not args.ledger and not ledger.exists():
                print("\n## Ledger line (no ledger found — file this)\n" + json.dumps(payload, ensure_ascii=False))
            else:
                fresh = append_line(ledger, payload)
                print(f"\nLEDGER: {'appended to' if fresh else 'already committed in'} {ledger} as {payload['run_id']}")
    except Fail as e:
        print(f"VALIDATION ERROR — fix the report and rerun:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
