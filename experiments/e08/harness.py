#!/usr/bin/env python3
"""E-08 harness (design.md). Deterministic runner and record-owner.

Subcommands:
  run        run all sessions (resumable: a session with a raw file is skipped)
  judge      haiku yes/no on each probe response
  finalize   aggregate, append one experiment line per family to the ledger

Raw evidence: raw/<family>-<arm>-<rep>.json, one file per 5-turn session.
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

E08 = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(E08, "raw")
MATERIALS = json.load(open(os.path.join(E08, "materials.json")))
CONTRACT = os.path.join(E08, "contract.md")
LEDGER = os.path.join(E08, "..", "..", "ledger", "runs.jsonl")
REPS = 5
FAMILIES = {"opus": ["stock", "sysprompt", "claudemd"],
            "kimi": ["sysprompt", "claudemd"]}


def sha16(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def parse_cli_json(stdout):
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def call(family, arm, prompt, cwd, sid, env):
    base = ["claude", "-p", "--model", "opus"] if family == "opus" else ["claude-kimi", "-p"]
    cmd = base + ["--output-format", "json"]
    if sid:
        cmd += ["--resume", sid]
    if arm == "sysprompt":
        cmd += ["--append-system-prompt-file", CONTRACT]
    cmd.append(prompt)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=420,
                       env=env)
    payload = parse_cli_json(p.stdout)
    if not payload:
        raise RuntimeError(f"unparseable output (exit {p.returncode}): {p.stderr[-300:]}")
    return payload


def one_session(family, arm, rep):
    out_path = os.path.join(RAW, f"{family}-{arm}-{rep}.json")
    if os.path.exists(out_path):
        return f"skip {os.path.basename(out_path)}"
    env = dict(os.environ)
    turns = []
    try:
        with tempfile.TemporaryDirectory(prefix=f"e08-{family}-{arm}-{rep}-") as cwd:
            if arm == "claudemd":
                with open(os.path.join(cwd, "CLAUDE.md"), "w") as f:
                    f.write(open(CONTRACT).read())
            if family == "kimi":
                env["CLAUDE_KIMI_SLOT_FILE"] = os.path.join(cwd, "slot")
            sid = None
            for i, filler in enumerate(MATERIALS["fillers"], 1):
                payload = call(family, arm, filler, cwd, sid, env)
                sid = payload["session_id"]
                if family == "kimi" and "CLAUDE_KIMI_SLOT" not in env:
                    env["CLAUDE_KIMI_SLOT"] = open(env["CLAUDE_KIMI_SLOT_FILE"]).read().strip()
                turns.append({"turn": i, "kind": "filler",
                              "output_tokens": payload["usage"]["output_tokens"],
                              "result_head": (payload.get("result") or "")[:60]})
            payload = call(family, arm, MATERIALS["probe"]["prompt"], cwd, sid, env)
            u = payload["usage"]
            turns.append({"turn": 5, "kind": "probe",
                          "output_tokens": u["output_tokens"],
                          "input_tokens": u.get("input_tokens"),
                          "cache_read_input_tokens": u.get("cache_read_input_tokens"),
                          "cache_creation_input_tokens": u.get("cache_creation_input_tokens")})
            rec = {"family": family, "arm": arm, "rep": rep, "session_id": sid,
                   "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "error": None, "turns": turns, "result": payload.get("result")}
    except Exception as e:
        rec = {"family": family, "arm": arm, "rep": rep,
               "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "error": str(e)[:300], "turns": turns, "result": None}
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f)
    os.rename(tmp, out_path)
    return f"done {os.path.basename(out_path)} err={rec['error']}"


def metrics(text, banned):
    low = text.lower()
    return {"banned_hits": sum(low.count(p) for p in banned),
            "emdash": text.count("—"),
            "chars": len(text)}


def banned_list():
    return [p.strip().lower() for p in re.findall(
        r'"([^"]+)"', open(CONTRACT).read().split("Never use these")[1].split("\n")[0])]


def load_raw():
    return [json.load(open(os.path.join(RAW, n)))
            for n in sorted(os.listdir(RAW)) if n.endswith(".json")]


def cmd_run():
    os.makedirs(RAW, exist_ok=True)
    jobs = [(f, a, r) for f, arms in FAMILIES.items()
            for a in arms for r in range(1, REPS + 1)]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(lambda j: one_session(*j), jobs):
            print(msg, flush=True)


def cmd_judge():
    recs = [r for r in load_raw() if r["result"] and "judge" not in r]
    def judge(rec):
        prompt = (f"{MATERIALS['probe']['judge']}\n\n--- RESPONSE ---\n"
                  f"{rec['result']}\n---\nReply with exactly one word: yes or no.")
        p = subprocess.run(["claude", "-p", "--model", "haiku", prompt],
                           capture_output=True, text=True, timeout=120)
        v = p.stdout.strip().lower().rstrip(".!")
        rec["judge"] = v if v in ("yes", "no") else f"invalid:{v[:40]}"
        path = os.path.join(RAW, f"{rec['family']}-{rec['arm']}-{rec['rep']}.json")
        with open(path, "w") as f:
            json.dump(rec, f)
        return f"{os.path.basename(path)} -> {rec['judge']}"
    with ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(judge, recs):
            print(msg, flush=True)


def cmd_finalize():
    banned = banned_list()
    now = datetime.now(timezone.utc)
    for fam, arms in FAMILIES.items():
        arms_out = {}
        for arm in arms:
            recs = [r for r in load_raw() if r["family"] == fam and r["arm"] == arm]
            ok = [r for r in recs if r["result"]]
            toks = [r["turns"][-1]["output_tokens"] for r in ok]
            ctx = [(r["turns"][-1].get("cache_read_input_tokens") or 0) +
                   (r["turns"][-1].get("cache_creation_input_tokens") or 0) +
                   (r["turns"][-1].get("input_tokens") or 0) for r in ok]
            ms = [metrics(r["result"], banned) for r in ok]
            arms_out[arm] = {
                "n": len(ok), "errors": len(recs) - len(ok),
                "probe_output_tokens": {"mean": round(statistics.mean(toks), 1),
                                        "stdev": round(statistics.stdev(toks), 1) if len(toks) > 1 else 0,
                                        "min": min(toks), "max": max(toks)} if toks else None,
                "probe_context_tokens_mean": round(statistics.mean(ctx), 0) if ctx else None,
                "banned_hits_total": sum(m["banned_hits"] for m in ms),
                "emdash_mean": round(statistics.mean(m["emdash"] for m in ms), 1) if ms else None,
                "chars_mean": round(statistics.mean(m["chars"] for m in ms), 0) if ms else None,
                "judge_yes": sum(1 for r in ok if r.get("judge") == "yes"),
                "filler_output_tokens_mean": round(statistics.mean(
                    t["output_tokens"] for r in ok for t in r["turns"][:-1]), 1) if ok else None}
        payload = {"type": "experiment", "experiment": "E-08", "family": fam,
                   "reps": REPS, "turns_per_session": 5, "probe": "e07-T2",
                   "arms": arms_out, "banned_phrases": banned,
                   "contract_sha256_16": sha16(CONTRACT),
                   "harness_sha256_16": sha16(os.path.abspath(__file__)),
                   "materials_sha256_16": sha16(os.path.join(E08, "materials.json")),
                   "raw_dir": "experiments/e08/raw"}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
        line = {"schema_version": 2, "type": "experiment",
                "run_id": f"r-{now:%Y%m%d}-{digest}",
                "date": now.isoformat(timespec="seconds"),
                **{k: v for k, v in payload.items() if k != "type"}}
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
        print(json.dumps(arms_out, indent=1))


if __name__ == "__main__":
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    if sub == "run":
        cmd_run()
    elif sub == "judge":
        cmd_judge()
    elif sub == "finalize":
        cmd_finalize()
    else:
        print(__doc__)
        sys.exit(2)
