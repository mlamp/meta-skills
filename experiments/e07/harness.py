#!/usr/bin/env python3
"""E-07 harness. Deterministic runner and record-owner (design.md).

Subcommands:
  baseline           run arm stock (opus: all tasks; kimi: T2), 5 reps
  scan               candidate-tic hits over baseline responses
  arms               run arms sysprompt + claudemd (contract.md must exist)
  judge              haiku yes/no per response: does it answer the task?
  finalize           aggregate, append one experiment line per family to ledger

Raw evidence: raw/<family>-<task>-<arm>-<rep>.json. Existing raw files are
never re-run (delete a file to redo it), so every subcommand is resumable.
Run from the repo root.
"""

import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

E07 = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(E07, "raw")
TASKS = json.load(open(os.path.join(E07, "tasks.json")))
CONTRACT = os.path.join(E07, "contract.md")
LEDGER = os.path.join(E07, "..", "..", "ledger", "runs.jsonl")
REPS = 5
FAMILIES = {"opus": ["T1", "T2", "T3"], "kimi": ["T2"]}
ARMS = ["stock", "sysprompt", "claudemd"]

CANDIDATES = [
    "load-bearing", "worth stating plainly", "here's the honest truth",
    "the real tension", "carry the argument", "worth noting", "it's worth",
    "importantly", "great question", "absolutely right", "delve",
    "let's dive", "in summary", "to summarize", "the key insight",
    "at its core", "fundamentally", "essentially", "robust", "comprehensive",
    "seamless", "elegant", "the honest answer", "crucially", "notably",
    "that said", "put simply", "bottom line", "the short answer",
]


def sha16(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def cmd_for(family, arm, prompt):
    base = ["claude", "-p", "--model", "opus"] if family == "opus" else ["claude-kimi", "-p"]
    cmd = base + ["--output-format", "json", prompt]
    if arm == "sysprompt":
        cmd += ["--append-system-prompt-file", CONTRACT]
    return cmd


def one_run(family, task, arm, rep):
    out_path = os.path.join(RAW, f"{family}-{task}-{arm}-{rep}.json")
    if os.path.exists(out_path):
        return f"skip {os.path.basename(out_path)}"
    prompt = TASKS[task]["prompt"]
    with tempfile.TemporaryDirectory(prefix=f"e07-{family}-{task}-{arm}-") as cwd:
        if arm == "claudemd":
            with open(os.path.join(cwd, "CLAUDE.md"), "w") as f:
                f.write(strip_frontmatter(open(CONTRACT).read()))
        try:
            p = subprocess.run(cmd_for(family, arm, prompt), capture_output=True,
                               text=True, cwd=cwd, timeout=420)
            payload = parse_cli_json(p.stdout)
            rec = {"family": family, "task": task, "arm": arm, "rep": rep,
                   "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "exit": p.returncode,
                   "error": None if payload else (p.stderr[-500:] or "unparseable"),
                   "result": payload.get("result") if payload else None,
                   "output_tokens": (payload.get("usage") or {}).get("output_tokens") if payload else None,
                   "num_turns": payload.get("num_turns") if payload else None}
        except subprocess.TimeoutExpired:
            rec = {"family": family, "task": task, "arm": arm, "rep": rep,
                   "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "exit": None, "error": "timeout 420s", "result": None,
                   "output_tokens": None, "num_turns": None}
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f)
    os.rename(tmp, out_path)
    return f"done {os.path.basename(out_path)} err={rec['error']}"


def parse_cli_json(stdout):
    # claude-kimi prefixes a "slot" line; find the JSON object line.
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip()
    return text


def run_cells(arms):
    os.makedirs(RAW, exist_ok=True)
    jobs = [(fam, task, arm, rep)
            for fam, tasks in FAMILIES.items()
            for task in tasks for arm in arms for rep in range(1, REPS + 1)]
    workers = {"opus": 4, "kimi": 2}
    with ThreadPoolExecutor(max_workers=5) as ex:
        # kimi capped implicitly by slot pool; interleave as submitted
        for msg in ex.map(lambda j: one_run(*j), jobs):
            print(msg, flush=True)


def load_raw(pred):
    out = []
    for name in sorted(os.listdir(RAW)):
        if name.endswith(".json"):
            rec = json.load(open(os.path.join(RAW, name)))
            if pred(rec):
                out.append(rec)
    return out


def metrics(text):
    low = text.lower()
    hits = {p: low.count(p) for p in CANDIDATES if low.count(p)}
    return {"phrase_hits": hits,
            "emdash": text.count("—"),
            "semicolons": text.count(";"),
            "bullets": len(re.findall(r"^\s*[-*] ", text, re.M)),
            "headings": len(re.findall(r"^#{1,6} ", text, re.M)),
            "chars": len(text)}


def cmd_scan():
    recs = load_raw(lambda r: r["arm"] == "stock" and r["result"])
    total = {}
    for r in recs:
        for p, n in metrics(r["result"])["phrase_hits"].items():
            total[p] = total.get(p, 0) + n
    print(f"{len(recs)} baseline responses")
    for p, n in sorted(total.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {p}")
    agg = {}
    for r in recs:
        m = metrics(r["result"])
        agg.setdefault(r["family"], []).append((m["emdash"], m["chars"], r["output_tokens"]))
    for fam, rows in agg.items():
        print(f"{fam}: mean emdash {statistics.mean(x[0] for x in rows):.1f}, "
              f"mean chars {statistics.mean(x[1] for x in rows):.0f}, "
              f"mean out_tokens {statistics.mean(x[2] for x in rows if x[2]):.0f}")


def cmd_judge():
    recs = load_raw(lambda r: r["result"] and "judge" not in r)
    def judge(rec):
        q = TASKS[rec["task"]]["judge"]
        prompt = (f"{q}\n\n--- RESPONSE ---\n{rec['result']}\n---\n"
                  "Reply with exactly one word: yes or no.")
        p = subprocess.run(["claude", "-p", "--model", "haiku", prompt],
                           capture_output=True, text=True, timeout=120)
        verdict = p.stdout.strip().lower().rstrip(".!")
        rec["judge"] = verdict if verdict in ("yes", "no") else f"invalid:{verdict[:40]}"
        path = os.path.join(RAW, f"{rec['family']}-{rec['task']}-{rec['arm']}-{rec['rep']}.json")
        with open(path, "w") as f:
            json.dump(rec, f)
        return f"{os.path.basename(path)} -> {rec['judge']}"
    with ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(judge, recs):
            print(msg, flush=True)


def cmd_finalize():
    banned = [p.strip().lower() for p in
              re.findall(r'"([^"]+)"', open(CONTRACT).read().split("Never use these")[1].split("\n")[0])]
    now = datetime.now(timezone.utc)
    for fam, tasks in FAMILIES.items():
        arms_out = {}
        for arm in ARMS:
            recs = load_raw(lambda r: r["family"] == fam and r["arm"] == arm)
            ok = [r for r in recs if r["result"]]
            per_task = {}
            for task in tasks:
                tr = [r for r in ok if r["task"] == task]
                toks = [r["output_tokens"] for r in tr if r["output_tokens"]]
                ms = [metrics(r["result"]) for r in tr]
                per_task[task] = {
                    "n": len(tr),
                    "output_tokens": {"mean": round(statistics.mean(toks), 1),
                                      "stdev": round(statistics.stdev(toks), 1) if len(toks) > 1 else 0,
                                      "min": min(toks), "max": max(toks)} if toks else None,
                    "banned_hits_total": sum(sum(n for p, n in m["phrase_hits"].items() if p in banned) for m in ms),
                    "candidate_hits_total": sum(sum(m["phrase_hits"].values()) for m in ms),
                    "emdash_mean": round(statistics.mean(m["emdash"] for m in ms), 1) if ms else None,
                    "chars_mean": round(statistics.mean(m["chars"] for m in ms), 0) if ms else None,
                    "judge_yes": sum(1 for r in tr if r.get("judge") == "yes"),
                    "errors": len(recs) - len(ok)}
            arms_out[arm] = per_task
        payload = {"schema_version": 2, "type": "experiment", "experiment": "E-07",
                   "family": fam, "reps": REPS, "tasks": tasks, "arms": arms_out,
                   "banned_phrases": banned,
                   "contract_sha256_16": sha16(CONTRACT),
                   "harness_sha256_16": sha16(os.path.abspath(__file__)),
                   "tasks_sha256_16": sha16(os.path.join(E07, "tasks.json")),
                   "raw_dir": "experiments/e07/raw"}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
        line = dict(schema_version=2, type="experiment",
                    run_id=f"r-{now:%Y%m%d}-{digest}",
                    date=now.isoformat(timespec="seconds"),
                    **{k: payload[k] for k in payload
                       if k not in ("schema_version", "type")})
        s = json.dumps(line)
        with open(LEDGER, "rb") as f:
            data = f.read()
        if not data.endswith(b"\n"):
            sys.exit("ledger does not end in newline")
        if line["run_id"].encode() in data:
            print(f"{fam}: run_id {line['run_id']} already committed, skipping")
            continue
        fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND)
        os.write(fd, s.encode() + b"\n")
        os.fsync(fd)
        os.close(fd)
        print(f"committed {line['run_id']} ({fam})")
        print(json.dumps(arms_out, indent=1)[:2000])


if __name__ == "__main__":
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    if sub == "baseline":
        run_cells(["stock"])
    elif sub == "scan":
        cmd_scan()
    elif sub == "arms":
        if not os.path.exists(CONTRACT):
            sys.exit("contract.md missing — write it after scan")
        run_cells(["sysprompt", "claudemd"])
    elif sub == "judge":
        cmd_judge()
    elif sub == "finalize":
        cmd_finalize()
    else:
        print(__doc__)
        sys.exit(2)
