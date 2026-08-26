#!/usr/bin/env python3
"""Measure the cold-reader qualification suite without spending its one attempt.

The real gate is one-shot per key: `attempt.json` is created O_EXCL, case records
refuse overwrite, and the measured gate demands `passed: true`. It is also strict —
every assertion must pass in every repetition for both readers. Spending it blind
costs a burned key, a new freeze, and a new measured id.

This runs the same cases through the same code path and writes nothing: no
namespace, no attempt marker, no ledger row, no raw record. It calls `case_prompt`,
`run_with_transport_retry` and `grade_case` directly; only `cmd_cold_reader` writes.

`case_prompt` builds from a case's `question` and `items` only and never reads
`expected`, so the model sees exactly what the gate would send it. The answer key
stays out of the prompt.

This file is deliberately NOT a frozen input. FREEZE_INPUTS is a fixed tuple, so
adding it changes no hash and no measured id. Keep it that way: a measurement tool
should be improvable without re-freezing the experiment it measures.

Use it to answer two questions before spending the attempt:

  --reps 5    would the gate pass right now?
  --classify  is each failure the same answer every time, or does it vary?

A deterministic failure points at the case key or the catalog wording. A varying
one points at reader instability. They need different fixes, and only the second
is helped by repetition tolerance.

Reading the results is not licence to tune the frozen inputs until the gate opens.
Correct a key that contradicts the catalog's own definitions; report the rest.
"""

import argparse
import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402


def run_case(profile, case):
    """Return (ok, failing_assertions). Never raises, never writes."""
    try:
        payload, _meta, _attempts = H.run_with_transport_retry(
            profile, H.case_prompt(case), H.case_schema(case)
        )
    except Exception as exc:  # transport, format and identity failures all fail the case
        return False, [{"assertion": f"<{type(exc).__name__}>",
                        "actual": str(exc)[:200], "expected": "-"}]
    graded = H.grade_case(case, payload)
    return all(a["pass"] for a in graded), [a for a in graded if not a["pass"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reps", type=int, default=5,
                        help="repetitions per case per reader (gate uses 5)")
    parser.add_argument("--cases", nargs="+",
                        help="case ids to run (default: the whole qualification suite)")
    parser.add_argument("--profiles", nargs="+",
                        help="reader profiles (default: the required qualification readers)")
    parser.add_argument("--classify", action="store_true",
                        help="group each failing assertion by the distinct wrong answers seen")
    args = parser.parse_args()

    suite = H.load_json(H.DATA_FILES["cold_reader_cases.json"])
    by_id = {case["id"]: case for case in suite["qualification"]["cases"]}
    case_ids = args.cases or list(by_id)
    unknown = [cid for cid in case_ids if cid not in by_id]
    if unknown:
        raise SystemExit(f"unknown case ids: {unknown}")

    profiles = H.profile_map()
    names = args.profiles or H.load_json(H.DATA_FILES["models.json"])["qualification_profiles"]

    clean = collections.Counter()
    attempted = collections.Counter()
    elapsed = collections.Counter()
    observed = collections.defaultdict(list)
    expected_of = {}

    started = time.monotonic()
    for name in names:
        profile = profiles[name]
        for rep in range(1, args.reps + 1):
            for cid in case_ids:
                call_started = time.monotonic()
                ok, failures = run_case(profile, by_id[cid])
                took = time.monotonic() - call_started
                attempted[name] += 1
                elapsed[name] += took
                clean[name] += ok
                for failure in failures:
                    key = (name, cid, failure["assertion"])
                    observed[key].append(json.dumps(failure["actual"], sort_keys=True))
                    expected_of[key] = json.dumps(failure["expected"], sort_keys=True)
                detail = "" if ok else "  " + ", ".join(f["assertion"] for f in failures[:4])
                print(f"{name:16s} rep={rep} {cid} {'pass' if ok else 'FAIL':4s} {took:5.1f}s{detail}",
                      flush=True)

    print("\n" + "=" * 66)
    total_clean = sum(clean.values())
    total_runs = sum(attempted.values())
    for name in names:
        runs = attempted[name]
        print(f"{name:16s} {clean[name]}/{runs} case-reps clean"
              f"   mean {elapsed[name]/runs:.1f}s/call   total {elapsed[name]/60:.1f}m")
    print(f"\nOVERALL {total_clean}/{total_runs} case-reps clean"
          f"; wall clock {(time.monotonic()-started)/60:.1f} min")
    full_suite = set(case_ids) == set(by_id) and args.reps == suite["qualification"]["repetitions_per_profile"]
    if full_suite:
        print("VERDICT:", "would PASS the gate" if total_clean == total_runs else "would BURN the gate")
    else:
        print("VERDICT: partial run — not a gate prediction")

    if observed:
        print("\nfailing assertions:")
        for key in sorted(observed):
            name, cid, assertion = key
            values = observed[key]
            distinct = sorted(set(values))
            kind = "deterministic" if len(distinct) == 1 else "varying"
            print(f"  {name:16s} {cid} {assertion:22s} {len(values)}/{args.reps} {kind}")
            if args.classify:
                print(f"{'':22s}expected: {expected_of[key][:88]}")
                for value in distinct:
                    print(f"{'':22s}actual  : {value[:88]}")

    return 0 if total_clean == total_runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
