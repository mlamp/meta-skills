#!/usr/bin/env python3
"""E-03 close-out: smell persistence across version pairs (C07).

Pairs each e03-* adjudication (old snapshot) with the adj-20260723 batch
(current snapshot, E-02) of the same skill and reviewer family. Fix-worthy
clusters are matched on (smell, file) — line numbers don't survive across
versions, so location is dropped from the key (recorded matching rule).

persisted = old fix-worthy (smell, file) also fix-worthy in current
resolved  = old fix-worthy, absent in current
new       = current fix-worthy, absent in old

Run from the repo root; prints the table, writes nothing.
"""

import json
from collections import defaultdict

old, cur = {}, {}
for line in open("ledger/runs.jsonl"):
    r = json.loads(line)
    if r.get("type") != "adjudication" or r.get("mode") != "spot-check":
        continue
    skill = r["target"]["path"].split("fixtures/real/")[1].split("/")[0]
    fam = "kimi" if "kimi" in r.get("reviewer_model", "") or "kimi" in r["batch_id"] else "fable"
    keys = {(c["smell"], c["location"].split(":")[0])
            for c in r["clusters"] if c["verdict"] == "fix-worthy"}
    snap = r["target"]["path"].split("/")[-1]
    dest = old if r["batch_id"].startswith("e03-") else cur
    dest[(skill, fam)] = {"keys": keys, "snap": snap, "batch": r["batch_id"]}

tot_p = tot_r = tot_n = 0
print(f"{'pair':<38} {'old':>3} {'cur':>3} {'persist':>7} {'resolved':>8} {'new':>4}")
for pair in sorted(old):
    if pair not in cur:
        print(f"{pair[0]+'/'+pair[1]:<38} old only — no current batch")
        continue
    o, c = old[pair]["keys"], cur[pair]["keys"]
    p, r_, n = len(o & c), len(o - c), len(c - o)
    tot_p, tot_r, tot_n = tot_p + p, tot_r + r_, tot_n + n
    print(f"{pair[0]+'/'+pair[1]:<38} {len(o):>3} {len(c):>3} {p:>7} {r_:>8} {n:>4}"
          f"   {old[pair]['snap']} -> {cur[pair]['snap']}")
    for k in sorted(o & c):
        print(f"    persisted: {k[0]} @ {k[1]}")

denom = tot_p + tot_r
print(f"\ntotals: persisted {tot_p}, resolved {tot_r}, new {tot_n}"
      f"  — persistence rate {tot_p}/{denom} = {tot_p/denom:.2f}" if denom else "no pairs")
print("current-only batches (no old pair):",
      [f"{k[0]}/{k[1]}" for k in cur if k not in old])
