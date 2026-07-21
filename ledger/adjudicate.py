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

Spot-check mode (E-02 protocol): real fixtures have no manifest, so there is
no auto-match and no recall. Every finding in the batch is clustered (same
smell + same file + overlapping spans, deterministic sweep) and adjudicated by
the user: fix-worthy | not-fix-worthy | wrong-evidence. Only fix-worthy is a
true positive for headline (strict) precision; fix-worthy + not-fix-worthy is
the secondary (grounded) precision. The worksheet is output-only except the
verdict and note columns: commit re-derives clusters from the ledger and
refuses on digest mismatch, row drift, or a blank/unknown verdict. Recall and
manifest fields are absent, never zero. One spot-check adjudication line per
batch may exist; corrections use --supersedes with a new line, never an edit.

  adjudicate.py spot-match  --ledger F --out worksheet.tsv BATCH_ID [BATCH_ID...]
  adjudicate.py spot-commit --ledger F --worksheet worksheet.tsv [--supersedes ADJ_ID]
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
    # No whole-text strip: it would eat the last row's trailing tab when the
    # verdict cell is empty, turning "verdict missing" into a field-count error.
    rows = Path(args.worksheet).read_text(encoding="utf-8").split("\n")
    while rows and not rows[-1].strip():
        rows.pop()
    verdicts = {}  # (batch, cluster_no) -> verdict
    for lineno, row in enumerate(rows[1:], start=2):
        parts = row.split("\t")
        if len(parts) == 7:
            parts.append("")  # editor stripped the trailing tab of an empty verdict
        if len(parts) != 8:
            die(f"worksheet line {lineno}: has {len(parts)} fields, want 8: {row!r}")
        b, cno, smell, loc, run_list, n_runs, why, verdict = parts
        verdict = verdict.strip()
        if not verdict:
            die(f"worksheet line {lineno}: cluster {b}#{cno} verdict is empty — "
                f"fill the last column with flaw:<n> | pre-existing | fp")
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


# ---------------------------------------------------------------------------
# Spot-check mode (E-02): manifest-less real fixtures, user verdicts.
# Everything below is additive; planted-mode functions above are unchanged.

SPOT_VERDICTS = re.compile(r"^(fix-worthy|not-fix-worthy|wrong-evidence)$")
SPOT_HEADER = ("batch\tcluster\tsmell\tlocation\truns\tn_runs\tmembers"
               "\texample_why\tverdict\tnote")
SPOT_PAD = 2  # line tolerance when merging spans, same as planted cluster()

SMELL_CATEGORY = {}
for _cat, _ids in (("trigger", ("CSD", "USN", "NTPD", "MUR")),
                   ("instruction", ("TSW", "SOC", "TOB", "MDT", "MT")),
                   ("grounding", ("ME", "TSS")),
                   ("verification", ("NVS", "EWP", "NAH", "RL", "NPT", "NG", "BG", "MC")),
                   ("economy", ("UD", "MUS")),
                   ("static", ("FM-parse", "LSN", "LSD", "XID", "LSB", "BP", "REF"))):
    for _s in _ids:
        SMELL_CATEGORY[_s] = _cat


def spot_findings(runs):
    """Every finding across a batch's runs, normalized. (seq, idx) is the
    stable identity a verdict traces back to."""
    out = []
    for r in runs:
        for idx, f in enumerate(r["findings"]):
            fname, start, end = ((None, None, None) if f["location"] == "static"
                                 else parse_loc(f["location"]))
            out.append({"seq": r["batch_seq"], "idx": idx, "smell": f["smell_id"],
                        "file": fname, "start": start, "end": end,
                        "why": " ".join(f["why"].split())})
    return out


def spot_cluster(findings, pad=SPOT_PAD):
    """Deterministic clustering: same (file, smell), spans merged by a sweep
    over start-sorted intervals with `pad` lines of tolerance. Span-less
    findings (static auto-findings) form one cluster per (file, smell).
    Canonical order: (file, smell, start)."""
    groups = {}
    for f in findings:
        groups.setdefault((f["file"] or "", f["smell"]), []).append(f)
    clusters = []
    for (fname, smell), members in sorted(groups.items()):
        spanless = sorted((m for m in members if m["start"] is None),
                          key=lambda m: (m["seq"], m["idx"]))
        if spanless:
            clusters.append({"smell": smell, "file": fname or None,
                             "start": None, "end": None, "members": spanless})
        cur = None
        for m in sorted((m for m in members if m["start"] is not None),
                        key=lambda m: (m["start"], m["end"], m["seq"], m["idx"])):
            if cur and m["start"] <= cur["end"] + pad:
                cur["members"].append(m)
                cur["end"] = max(cur["end"], m["end"])
            else:
                cur = {"smell": smell, "file": fname, "start": m["start"],
                       "end": m["end"], "members": [m]}
                clusters.append(cur)
    return clusters


def spot_digest(runs, clusters):
    """Binds a worksheet to the exact review lines and derived clustering."""
    basis = [sorted(r["run_id"] for r in runs),
             [[c["smell"], c["file"] or "", [[m["seq"], m["idx"]] for m in c["members"]]]
              for c in clusters]]
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:16]


def spot_loc(c):
    return f"{c['file']}:{c['start']}-{c['end']}" if c["file"] and c["start"] is not None \
        else (f"{c['file']}:static" if c["file"] else "static")


def cmd_spot_match(args):
    runs_by_batch = load_runs(args.ledger, args.batch_ids)
    comments, rows = [], [SPOT_HEADER]
    for b, runs in runs_by_batch.items():
        findings = spot_findings(runs)
        clusters = spot_cluster(findings)
        comments.append(f"# {b} digest={spot_digest(runs, clusters)} "
                        f"runs={len(runs)} findings={len(findings)} clusters={len(clusters)}")
        print(f"\n===== {b} — spot-check: {len(findings)} findings, "
              f"{len(clusters)} clusters =====")
        for i, c in enumerate(clusters, 1):
            seqs = sorted({m["seq"] for m in c["members"]})
            mem = ",".join(f"{m['seq']}:{m['idx']}" +
                           (f"@{m['start']}-{m['end']}" if m["start"] is not None else "")
                           for m in c["members"])
            why = c["members"][0]["why"][:140]
            print(f"   [{b}#{i}] {c['smell']:5} {spot_loc(c)}  runs {seqs}: {why[:110]}")
            rows.append(f"{b}\t{i}\t{c['smell']}\t{spot_loc(c)}\t"
                        f"{','.join(map(str, seqs))}\t{len(seqs)}\t{mem}\t{why}\t\t")
    Path(args.out).write_text("\n".join(comments + rows) + "\n", encoding="utf-8")
    print(f"\nworksheet: {args.out} — fill 'verdict' with "
          f"fix-worthy | not-fix-worthy | wrong-evidence; 'note' is optional free text")


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"per_run": [round(v, 4) for v in vals],
            "mean": round(statistics.mean(vals), 4),
            "min": round(min(vals), 4), "max": round(max(vals), 4),
            "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0}


def cmd_spot_commit(args):
    lines = Path(args.worksheet).read_text(encoding="utf-8").split("\n")
    digests, body = {}, []
    for lineno, line in enumerate(lines, start=1):
        if line.startswith("#"):
            m = re.match(r"^# (\S+) digest=([0-9a-f]{16}) ", line)
            if m:
                digests[m.group(1)] = m.group(2)
        else:
            body.append((lineno, line))
    while body and not body[-1][1].strip():
        body.pop()
    if not body or body[0][1] != SPOT_HEADER:
        die(f"worksheet header mismatch — want exactly: {SPOT_HEADER!r}")
    verdicts, notes = {}, {}
    for lineno, row in body[1:]:
        parts = row.split("\t")
        if len(parts) in (8, 9):  # editor stripped trailing tabs of empty cells
            parts += [""] * (10 - len(parts))
        if len(parts) != 10:
            die(f"worksheet line {lineno}: has {len(parts)} fields, want 10: {row!r}")
        b, cno, smell, loc, run_list, n_runs, mem, why, verdict, note = parts
        verdict = verdict.strip()
        key = (b, int(cno))
        if key in verdicts:
            die(f"worksheet line {lineno}: duplicate row for cluster {b}#{cno}")
        if not verdict:
            die(f"worksheet line {lineno}: cluster {b}#{cno} verdict is empty — "
                f"fill with fix-worthy | not-fix-worthy | wrong-evidence")
        if not SPOT_VERDICTS.match(verdict):
            die(f"cluster {b}#{cno}: verdict {verdict!r} not in "
                f"fix-worthy | not-fix-worthy | wrong-evidence")
        verdicts[key] = verdict
        if note.strip():
            notes[key] = " ".join(note.split())

    batch_ids = sorted({b for b, _ in verdicts})
    runs_by_batch = load_runs(args.ledger, batch_ids)

    # double-commit guard: one live spot-check line per batch
    existing = {}
    for line in Path(args.ledger).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("type") == "adjudication" and r.get("mode") == "spot-check":
            existing.setdefault(r["batch_id"], []).append(r["adj_id"])

    committed = []
    for b, runs in runs_by_batch.items():
        prior = existing.get(b, [])
        live = [a for a in prior if a != args.supersedes]
        if live:
            die(f"batch {b} already has spot-check adjudication {live} — "
                f"pass --supersedes <adj_id> to record a correcting line")
        findings = spot_findings(runs)
        clusters = spot_cluster(findings)
        if b not in digests:
            die(f"worksheet has no digest comment for batch {b}")
        if digests[b] != spot_digest(runs, clusters):
            die(f"batch {b}: worksheet digest {digests[b]} does not match clusters "
                f"re-derived from the ledger — stale or hand-edited worksheet")
        want = {(b, i) for i in range(1, len(clusters) + 1)}
        got = {k for k in verdicts if k[0] == b}
        if want != got:
            die(f"batch {b}: worksheet rows {sorted(c for _, c in got)} do not match "
                f"derived clusters 1..{len(clusters)}")
        for i, c in enumerate(clusters, 1):
            c["verdict"] = verdicts[(b, i)]
            c["note"] = notes.get((b, i))

        seqs = [r["batch_seq"] for r in runs]
        cluster_of = {(m["seq"], m["idx"]): i
                      for i, c in enumerate(clusters, 1) for m in c["members"]}
        vc = {i: c["verdict"] for i, c in enumerate(clusters, 1)}
        per_run, strict, grounded = {}, [], []
        for r in runs:
            s = r["batch_seq"]
            total = len(r["findings"])
            fw = sum(1 for idx in range(total) if vc[cluster_of[(s, idx)]] == "fix-worthy")
            nfw = sum(1 for idx in range(total) if vc[cluster_of[(s, idx)]] == "not-fix-worthy")
            we = total - fw - nfw
            per_run[s] = {"findings": total, "fix_worthy": fw,
                          "not_fix_worthy": nfw, "wrong_evidence": we,
                          "precision_strict": round(fw / total, 4) if total else None,
                          "precision_grounded": round((fw + nfw) / total, 4) if total else None}
            strict.append(per_run[s]["precision_strict"])
            grounded.append(per_run[s]["precision_grounded"])
        pooled_total = sum(p["findings"] for p in per_run.values())
        pooled_fw = sum(p["fix_worthy"] for p in per_run.values())
        pooled_nfw = sum(p["not_fix_worthy"] for p in per_run.values())
        n_cl = len(clusters)
        vcounts = {v: sum(1 for c in clusters if c["verdict"] == v)
                   for v in ("fix-worthy", "not-fix-worthy", "wrong-evidence")}

        present = {s: {cluster_of[(s, idx)] for idx in range(per_run[s]["findings"])}
                   for s in seqs}
        fw_sets = {s: {i for i in present[s] if vc[i] == "fix-worthy"} for s in seqs}
        pairs = [(a, c) for i, a in enumerate(seqs) for c in seqs[i + 1:]]
        jac_all = [len(present[a] & present[c]) / len(present[a] | present[c])
                   for a, c in pairs if present[a] | present[c]]
        jac_fw = [len(fw_sets[a] & fw_sets[c]) / len(fw_sets[a] | fw_sets[c])
                  for a, c in pairs if fw_sets[a] | fw_sets[c]]
        flips = [i for i, c in enumerate(clusters, 1)
                 if 0 < len({m["seq"] for m in c["members"]}) < len(seqs)]

        def confirmed(keyfn):
            out = {}
            for i, c in enumerate(clusters, 1):
                k = keyfn(c)
                out.setdefault(k, {"fix-worthy": 0, "not-fix-worthy": 0,
                                   "wrong-evidence": 0})[c["verdict"]] += 1
            return dict(sorted(out.items()))

        dims = list(runs[0]["scores"].keys())
        score_stats = {d: {"values": [r["scores"][d] for r in runs],
                           "stdev": round(statistics.stdev([r["scores"][d] for r in runs]), 3)
                           if len(runs) > 1 else 0.0,
                           "range": max(r["scores"][d] for r in runs)
                           - min(r["scores"][d] for r in runs)}
                       for d in dims}
        payload = {
            "schema_version": 2,
            "type": "adjudication",
            "mode": "spot-check",
            "batch_id": b,
            "target": runs[0]["target"],
            "run_ids": [r["run_id"] for r in runs],
            "reviewer_model": runs[0]["reviewer"]["model"],
            "adjudicator": "user",
            "verdict_rubric": "fix-worthy | not-fix-worthy | wrong-evidence (E-02); "
                              "strict TP = fix-worthy only",
            "n_findings": pooled_total,
            "n_clusters": n_cl,
            "verdict_counts": vcounts,
            "clusters": [{"cluster": i, "smell": c["smell"],
                          "category": SMELL_CATEGORY.get(c["smell"], "unknown"),
                          "location": spot_loc(c),
                          "runs": sorted({m["seq"] for m in c["members"]}),
                          "members": [[m["seq"], m["idx"]] for m in c["members"]],
                          "verdict": c["verdict"],
                          **({"note": c["note"]} if c["note"] else {})}
                         for i, c in enumerate(clusters, 1)],
            "per_run": per_run,
            "precision": {
                "strict": {**(_stats(strict) or {}),
                           "pooled": round(pooled_fw / pooled_total, 4) if pooled_total else None},
                "grounded": {**(_stats(grounded) or {}),
                             "pooled": round((pooled_fw + pooled_nfw) / pooled_total, 4)
                             if pooled_total else None},
                "cluster_level": {
                    "strict": round(vcounts["fix-worthy"] / n_cl, 4) if n_cl else None,
                    "grounded": round((vcounts["fix-worthy"] + vcounts["not-fix-worthy"]) / n_cl, 4)
                    if n_cl else None}},
            "agreement": {
                "pairwise_jaccard_all": round(statistics.mean(jac_all), 4) if jac_all else None,
                "pairwise_jaccard_fix_worthy": round(statistics.mean(jac_fw), 4) if jac_fw else None,
                "cluster_flips": flips,
                "cluster_flip_rate": round(len(flips) / n_cl, 4) if n_cl else None},
            "score_stats": score_stats,
            "confirmed": {"by_file": confirmed(lambda c: c["file"] or "static"),
                          "by_smell": confirmed(lambda c: c["smell"]),
                          "by_category": confirmed(
                              lambda c: SMELL_CATEGORY.get(c["smell"], "unknown"))},
            "clustering": {"pad": SPOT_PAD, "n_clusters": n_cl,
                           "sensitivity": {"pad0": len(spot_cluster(findings, pad=0)),
                                           "pad5": len(spot_cluster(findings, pad=5))}},
            "worksheet_sha256_16": hashlib.sha256(
                Path(args.worksheet).read_bytes()).hexdigest()[:16],
            **({"supersedes": args.supersedes}
               if args.supersedes and args.supersedes in prior else {}),
            "notes": args.notes or "",
        }
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        payload["adj_id"] = "adj-" + now.strftime("%Y%m%d") + "-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()).hexdigest()[:10]
        payload["date"] = now.isoformat(timespec="seconds")
        if append_line(Path(args.ledger), {**payload, "run_id": payload["adj_id"]}):
            committed.append(payload["adj_id"])
        ps = payload["precision"]["strict"]
        print(f"{b}: strict precision mean {ps.get('mean')} (pooled {ps.get('pooled')}), "
              f"grounded pooled {payload['precision']['grounded'].get('pooled')}, "
              f"clusters {n_cl} {vcounts}, "
              f"jaccard_all {payload['agreement']['pairwise_jaccard_all']} "
              f"-> {payload['adj_id']}")
    print(f"committed {len(committed)} spot-check adjudication line(s)")


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
    sm = sub.add_parser("spot-match")
    sm.add_argument("batch_ids", nargs="+")
    sm.add_argument("--ledger", required=True)
    sm.add_argument("--out", required=True)
    sc = sub.add_parser("spot-commit")
    sc.add_argument("--ledger", required=True)
    sc.add_argument("--worksheet", required=True)
    sc.add_argument("--notes")
    sc.add_argument("--supersedes")
    args = ap.parse_args()
    {"match": cmd_match, "commit": cmd_commit,
     "spot-match": cmd_spot_match, "spot-commit": cmd_spot_commit}[args.cmd](args)


if __name__ == "__main__":
    main()
