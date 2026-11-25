#!/usr/bin/env python3
"""Mutation testing for contracts/guilt_split.py.

  python scripts/mutate.py              run every mutation (about 200, several minutes)
  python scripts/mutate.py --check      only verify that every mutation applies exactly once
  python scripts/mutate.py -k window    run mutations whose name contains "window"
  python scripts/mutate.py -j 2         parallel workers (default 2)
  python scripts/mutate.py --report docs/MUTATION.md

For each mutation a copy of the contract is written to a temp directory under the same file
name and the Direct Mode suite is run against it (GUILTSPLIT_CONTRACT). The mutant is KILLED
if any test fails. A SURVIVOR is reported, and the script exits 1 unless the survivor is
listed in EQUIVALENT below with a written reason (a change that cannot alter behaviour).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from mutations import MUTATIONS as PART1  # noqa: E402
from mutations_contract import MUTATIONS as PART2  # noqa: E402
from mutations_methods import MUTATIONS as PART3  # noqa: E402

SOURCE = ROOT / "contracts" / "guilt_split.py"
MUTATIONS = PART1 + PART2 + PART3

# name -> why the change cannot alter observable behaviour.
EQUIVALENT = {
    "event-unknown-type": (
        "Defensive guard for the real GenVM, where a TreeMap lookup with a key of the wrong type may "
        "raise instead of returning 'absent'. In Direct Mode the map is a plain dict, so the mutant "
        "behaves the same; only the live run can tell them apart."),
    "resolved-status": (
        "Redundant by construction: `verdict` is only written by `_settle`, which also sets status "
        "ASSESSED (or EXHAUSTED with verdict UNDETERMINED). No reachable state has a resolved verdict "
        "with another status."),
    "split-zeros": (
        "Redundant by construction: every case that is not resolved has all three shares at 0 "
        "(unsettled cases keep the initial zeros, UNDETERMINED decisions are 0/0/0). The guard only "
        "documents the rule."),
    "penalty-resolved": (
        "Redundant by construction: `penalty` is True only for TEAM_FORFEIT and SOLO_FORFEIT, which "
        "are resolved verdicts, so `case.penalty` alone gives the same answer in every reachable state."),
}

TIMEOUT = 240


def apply(src: str, old: str, new: str) -> str:
    return src.replace(old, new, 1)


def check_catalogue(src: str) -> int:
    bad = 0
    seen = set()
    for name, old, new in MUTATIONS:
        if name in seen:
            print("DUPLICATE NAME  ", name)
            bad += 1
        seen.add(name)
        n = src.count(old)
        if n != 1:
            print("APPLIES %d TIMES " % n, name)
            bad += 1
        elif old == new:
            print("NO-OP           ", name)
            bad += 1
    print("%d mutations, %d problems" % (len(MUTATIONS), bad))
    return bad


def run_one(item):
    name, old, new = item
    src = SOURCE.read_text(encoding="utf-8")
    mutant = apply(src, old, new)
    with tempfile.TemporaryDirectory(prefix="mut-") as tmp:
        path = Path(tmp) / SOURCE.name
        path.write_text(mutant, encoding="utf-8")
        env = dict(os.environ, GUILTSPLIT_CONTRACT=str(path))
        started = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
                 "--no-header"],
                cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=TIMEOUT,
            )
            killed = proc.returncode != 0
            tail = proc.stdout.strip().splitlines()
            first_fail = next((ln for ln in tail if ln.startswith("FAILED") or ln.startswith("ERROR")), "")
        except subprocess.TimeoutExpired:
            killed, first_fail = True, "timeout (counted as killed: the mutant hangs)"
        return name, killed, first_fail, time.time() - started


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("-k", dest="match", help="comma-separated name fragments")
    ap.add_argument("-j", dest="jobs", type=int, default=2)
    ap.add_argument("--report")
    args = ap.parse_args(argv)

    src = SOURCE.read_text(encoding="utf-8")
    if check_catalogue(src) != 0:
        return 2
    if args.check:
        return 0

    todo = [m for m in MUTATIONS if not args.match or any(k in m[0] for k in args.match.split(","))]
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for name, killed, how, secs in pool.map(run_one, todo):
            results.append((name, killed, how, secs))
            print("%-9s %-34s %5.1fs  %s" % ("killed" if killed else "SURVIVED", name, secs, how[:90]), flush=True)

    survivors = [r for r in results if not r[1]]
    unexplained = [r for r in survivors if r[0] not in EQUIVALENT]
    stale = [n for n in EQUIVALENT if any(r[0] == n and r[1] for r in results)]
    print()
    print("mutants: %d, killed: %d, survived: %d (explained equivalents: %d)" % (
        len(results), len(results) - len(survivors), len(survivors), len(survivors) - len(unexplained)))
    for n in stale:
        print("note: %s is listed as equivalent but was killed; drop it from EQUIVALENT" % n)

    if args.report:
        lines = ["# Mutation run", "",
                 "Mutants: %d. Killed: %d. Survived: %d." % (len(results), len(results) - len(survivors), len(survivors)),
                 ""]
        if survivors:
            lines += ["| Survivor | Why it cannot change behaviour |", "|---|---|"]
            for name, _k, _h, _s in survivors:
                lines.append("| `%s` | %s |" % (name, EQUIVALENT.get(name, "UNEXPLAINED")))
        else:
            lines.append("No survivors.")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")

    shutil.rmtree(ROOT / "artifacts", ignore_errors=True)
    for r in unexplained:
        print("UNEXPLAINED SURVIVOR:", r[0])
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
