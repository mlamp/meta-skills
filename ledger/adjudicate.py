#!/usr/bin/env python3
"""Eval-harness adjudicator: matches planted-fixture review findings to flaw
manifests and commits type:adjudication ledger lines (E-01 protocol; D-013).

Deterministic side of the record (D-015 rule of thumb): the model and the user
author verdicts in a TSV worksheet; this script does all matching, arithmetic,
serialization, and ledger writes. Nothing here is hand-assembled JSON.

Match rule (fixtures/README.md): a finding matches a planted flaw when the
smell IDs are equal and the cited span overlaps the flaw's span (spans file
<fixture>.spans.tsv beside the manifest), or when a static auto-finding's
check id equals the flaw's static tag. Smells are unique per manifest, so a
finding has at most one auto-match. Everything else is a cluster for user
adjudication: verdict `flaw:<n>` (near-match credit), `pre-existing`, or `fp`.

Usage:
  adjudicate.py match  --ledger F --out worksheet.tsv BATCH_ID [BATCH_ID...]
  adjudicate.py commit --ledger F --worksheet worksheet.tsv
"""
import argparse
import hashlib
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "finalize", REPO / "skills/review-skill/scripts/finalize.py")
_finalize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_finalize)
append_line = _finalize.append_line

VERDICTS = re.compile(r"^(flaw:\d+|pre-existing|fp)$")


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_runs(ledger, batch_ids):
    runs = {}
    for line in Path(ledger).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("type") == "review" and r.get("batch_id") in batch_ids:
            runs.setdefault(r["batch_id"], []).append(r)
    for b in batch_ids:
        if b not in runs:
            die(f"no review lines for batch {b} in {ledger}")
        runs[b].sort(key=lambda r: r["batch_seq"])
    return runs


def load_spans(fixture_path):
    fixture = Path(fixture_path)
    spans_file = fixture.parent / f"{fixture.name}.spans.tsv"
    if not spans_file.is_file():
        die(f"no spans file {spans_file}")
    flaws = {}
    rows = spans_file.read_text(encoding="utf-8").strip().split("\n")
    for row in rows[1:]:
        n, smell, fname, start, end, static = row.split("\t")
        flaws[int(n)] = {"n": int(n), "smell": smell, "file": fname,
                         "start": int(start), "end": int(end),
                         "static": None if static == "-" else static}
    return flaws, spans_file


def parse_loc(loc):
    m = re.match(r"^(.+):(\d+)-(\d+)$", loc)
    return (m.group(1), int(m.group(2)), int(m.group(3))) if m else (None, None, None)


def match_batch(runs, flaws):
    """Returns (per-run matched flaw sets, unmatched finding list)."""
    caught = {}     # seq -> set of flaw n
    unmatched = []  # {seq, idx, smell, location, file, start, end, why}
    for r in runs:
        seq = r["batch_seq"]
        caught[seq] = set()
        for idx, f in enumerate(r["findings"]):
            hit = None
            if f["location"] == "static":
                hit = next((fl["n"] for fl in flaws.values()
                            if fl["static"] == f["smell_id"]), None)
            else:
                fname, start, end = parse_loc(f["location"])
                for fl in flaws.values():
                    if (fl["smell"] == f["smell_id"] and fl["file"] == fname
                            and start is not None
                            and start <= fl["end"] and end >= fl["start"]):
                        hit = fl["n"]
                        break
            if hit is not None:
                caught[seq].add(hit)
            else:
                fname, start, end = parse_loc(f["location"])
                unmatched.append({"seq": seq, "idx": idx, "smell": f["smell_id"],
                                  "location": f["location"], "file": fname,
                                  "start": start, "end": end,
                                  "why": " ".join(f["why"].split())[:140]})
    return caught, unmatched


def cluster(unmatched):
    """Group unmatched findings by (smell, file, overlapping spans)."""
    clusters = []
    for u in unmatched:
        home = None
        for c in clusters:
            if c["smell"] == u["smell"] and c["file"] == u["file"]:
                if u["start"] is None or (u["start"] <= c["end"] + 2
                                          and u["end"] >= c["start"] - 2):
                    home = c
                    break
        if home:
            home["members"].append(u)
            if u["start"] is not None:
                home["start"] = min(home["start"], u["start"])
                home["end"] = max(home["end"], u["end"])
        else:
            clusters.append({"smell": u["smell"], "file": u["file"],
                             "start": u["start"] or 0, "end": u["end"] or 0,
                             "members": [u]})
    return clusters


def cmd_match(args):
    runs_by_batch = load_runs(args.ledger, args.batch_ids)
    out_rows = ["batch\tcluster\tsmell\tlocation\truns\tn_runs\texample_why\tverdict"]
    for b, runs in runs_by_batch.items():
        flaws, _ = load_spans(runs[0]["target"]["path"])
        caught, unmatched = match_batch(runs, flaws)
        print(f"\n===== {b} — auto-match =====")
        for n, fl in sorted(flaws.items()):
            seqs = sorted(s for s, c in caught.items() if n in c)
            mark = "MISSED-ALL" if not seqs else ("all" if len(seqs) == len(runs) else f"partial {seqs}")
            print(f"  flaw {n:2} {fl['smell']:5} {fl['file']}:{fl['start']}-{fl['end']}  caught: {mark}")
        cl = cluster(unmatched)
        print(f"  unmatched clusters: {len(cl)}")
        for i, c in enumerate(cl, 1):
            seqs = sorted({m['seq'] for m in c['members']})
            loc = f"{c['file']}:{c['start']}-{c['end']}" if c["file"] else "static"
            print(f"   [{b}#{i}] {c['smell']:5} {loc}  in runs {seqs}: {c['members'][0]['why'][:110]}")
            out_rows.append(f"{b}\t{i}\t{c['smell']}\t{loc}\t{','.join(map(str, seqs))}\t{len(seqs)}\t{c['members'][0]['why']}\t")
    Path(args.out).write_text("\n".join(out_rows) + "\n", encoding="utf-8")
    print(f"\nworksheet: {args.out} — fill the last column with flaw:<n> | pre-existing | fp")


def cmd_commit(args):
    rows = Path(args.worksheet).read_text(encoding="utf-8").strip().split("\n")
    verdicts = {}  # (batch, cluster_no) -> verdict
    for row in rows[1:]:
        parts = row.split("\t")
        if len(parts) != 8:
            die(f"worksheet row has {len(parts)} fields, want 8: {row!r}")
        b, cno, smell, loc, run_list, n_runs, why, verdict = parts
        verdict = verdict.strip()
        if not VERDICTS.match(verdict):
            die(f"cluster {b}#{cno}: verdict {verdict!r} not in flaw:<n> | pre-existing | fp")
        verdicts[(b, int(cno))] = verdict

    batch_ids = sorted({b for b, _ in verdicts} | set(args.batch_ids or []))
    runs_by_batch = load_runs(args.ledger, batch_ids)
    committed = []
    for b, runs in runs_by_batch.items():
        flaws, spans_file = load_spans(runs[0]["target"]["path"])
        caught, unmatched = match_batch(runs, flaws)
        cl = cluster(unmatched)
        for i, c in enumerate(cl, 1):
            if (b, i) not in verdicts:
                die(f"cluster {b}#{i} has no verdict in the worksheet")
            c["verdict"] = verdicts[(b, i)]
        n_flaws = len(flaws)
        seqs = [r["batch_seq"] for r in runs]

        # near-match credits extend per-run caught sets
        credited = {s: set(caught[s]) for s in seqs}
        for c in cl:
            if c["verdict"].startswith("flaw:"):
                n = int(c["verdict"].split(":")[1])
                if n not in flaws:
                    die(f"{b}: verdict credits flaw {n}, not in manifest")
                for m in c["members"]:
                    credited[m["seq"]].add(n)

        # precision: per run, TP = matched + credited + pre-existing members; FP = fp members
        per_run = {}
        for r in runs:
            s = r["batch_seq"]
            total = len(r["findings"])
            fp = sum(1 for c in cl if c["verdict"] == "fp"
                     for m in c["members"] if m["seq"] == s)
            per_run[s] = {"findings": total, "tp": total - fp, "fp": fp,
                          "recall": round(len(credited[s]) / n_flaws, 4),
                          "precision": round((total - fp) / total, 4) if total else None}
        recalls = [per_run[s]["recall"] for s in seqs]
        precisions = [per_run[s]["precision"] for s in seqs]
        union = set().union(*credited.values())
        flaw_rows = []
        for n, fl in sorted(flaws.items()):
            in_seqs = sorted(s for s in seqs if n in credited[s])
            flaw_rows.append({"n": n, "smell": fl["smell"],
                              "span": f"{fl['file']}:{fl['start']}-{fl['end']}",
                              "caught_in": in_seqs, "rate": round(len(in_seqs) / len(seqs), 2)})
        flips = [f["n"] for f in flaw_rows if 0 < len(f["caught_in"]) < len(seqs)]
        missed = [f["n"] for f in flaw_rows if not f["caught_in"]]
        # pairwise Jaccard agreement over credited flaw sets
        pairs = [(a, c) for i, a in enumerate(seqs) for c in seqs[i + 1:]]
        jac = [len(credited[a] & credited[c]) / len(credited[a] | credited[c])
               for a, c in pairs if credited[a] | credited[c]]
        dims = list(runs[0]["scores"].keys())
        score_stats = {d: {"values": [r["scores"][d] for r in runs],
                           "stdev": round(statistics.stdev([r["scores"][d] for r in runs]), 3),
                           "range": max(r["scores"][d] for r in runs) - min(r["scores"][d] for r in runs)}
                       for d in dims}
        payload = {
            "schema_version": 2,
            "type": "adjudication",
            "batch_id": b,
            "target": runs[0]["target"],
            "manifest_sha256_16": hashlib.sha256(
                (Path(runs[0]["target"]["path"]).parent /
                 f"{Path(runs[0]['target']['path']).name}.manifest.md").read_bytes()).hexdigest()[:16],
            "spans_sha256_16": hashlib.sha256(spans_file.read_bytes()).hexdigest()[:16],
            "run_ids": [r["run_id"] for r in runs],
            "reviewer_model": runs[0]["reviewer"]["model"],
            "n_planted": n_flaws,
            "per_flaw": flaw_rows,
            "recall": {"per_run": recalls, "mean": round(statistics.mean(recalls), 4),
                       "min": min(recalls), "max": max(recalls),
                       "stdev": round(statistics.stdev(recalls), 4),
                       "union": round(len(union) / n_flaws, 4)},
            "precision": {"per_run": precisions, "mean": round(statistics.mean(precisions), 4),
                          "min": min(precisions), "max": max(precisions),
                          "stdev": round(statistics.stdev(precisions), 4)},
            "agreement": {"pairwise_jaccard_mean": round(statistics.mean(jac), 4),
                          "flaw_flips": flips, "flaw_flip_rate": round(len(flips) / n_flaws, 4),
                          "missed_all": missed},
            "score_stats": score_stats,
            "adjudications": [{"cluster": i, "smell": c["smell"],
                               "location": f"{c['file']}:{c['start']}-{c['end']}" if c["file"] else "static",
                               "runs": sorted({m['seq'] for m in c['members']}),
                               "verdict": c["verdict"]} for i, c in enumerate(cl, 1)],
            "notes": args.notes or "",
        }
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        payload["adj_id"] = "adj-" + now.strftime("%Y%m%d") + "-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
        payload["date"] = now.isoformat(timespec="seconds")
        if append_line(Path(args.ledger), {**payload, "run_id": payload["adj_id"]}):
            committed.append(payload["adj_id"])
        print(f"{b}: recall mean {payload['recall']['mean']} (union {payload['recall']['union']}), "
              f"precision mean {payload['precision']['mean']}, "
              f"jaccard {payload['agreement']['pairwise_jaccard_mean']}, "
              f"flips {flips}, missed {missed} -> {payload['adj_id']}")
    print(f"committed {len(committed)} adjudication line(s)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match")
    m.add_argument("batch_ids", nargs="+")
    m.add_argument("--ledger", required=True)
    m.add_argument("--out", required=True)
    c = sub.add_parser("commit")
    c.add_argument("batch_ids", nargs="*")
    c.add_argument("--ledger", required=True)
    c.add_argument("--worksheet", required=True)
    c.add_argument("--notes")
    args = ap.parse_args()
    (cmd_match if args.cmd == "match" else cmd_commit)(args)


if __name__ == "__main__":
    main()
