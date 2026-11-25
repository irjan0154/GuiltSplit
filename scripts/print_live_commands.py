#!/usr/bin/env python3
"""Print the exact Studio inputs for the live run, from manifest.live.json.

  python scripts/print_live_commands.py            all steps
  python scripts/print_live_commands.py 3          only scenario 3

Run the scenarios one at a time. After each assess, read the GenVM result of the
transaction (it must say SUCCESS), then check the case with the read calls shown.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load() -> dict:
    path = ROOT / "manifest.live.json"
    if not path.exists():
        sys.exit("manifest.live.json is missing: run scripts/make_manifest.py --base-url <pinned URL>")
    return json.loads(path.read_text(encoding="utf-8"))


def q(value) -> str:
    return json.dumps(value, ensure_ascii=True)


def show_event(m: dict) -> None:
    e = m["event"]
    print("== 0. register_event (once, as the organizer account) ==")
    print("  event_id    =", q(e["event_id"]))
    print("  start       =", q(e["start"]))
    print("  end         =", q(e["end"]))
    print("  roster_size =", e["roster_size"])
    print("  ruling_base =", q(e["ruling_base"]))
    print()


def show_scenario(m: dict, s: dict) -> None:
    e, exp = m["event"], s["expected"]
    print("== %d. %s ==" % (s["n"], s["case_label"]))
    print("  propose_case:")
    print("    event_id      =", q(e["event_id"]))
    print("    case_label    =", q(s["case_label"]))
    print("    ruling_url    =", q(s["ruling_url"]))
    print("    ruling_sha256 =", q(s["sha256"]))
    print("    player_handle =", q(m["player_handle"]))
    print("  then assess(case_id)   (case_id is the value returned by propose_case)")
    print("  expect: verdict=%s reason=%s split=%d/%d/%d penalty=%s resolved=%s" % (
        exp["verdict"], exp["reason"], exp["player_bps"], exp["teammates_bps"],
        exp["second_place_bps"], exp["penalty"], exp["resolved"]))
    print("  read: get_case(case_id), get_split_bps(case_id), is_resolved(case_id), get_stats()")
    print()


def main(argv) -> int:
    m = load()
    wanted = None
    if len(argv) > 1:
        wanted = int(argv[1])
    if wanted is None:
        show_event(m)
    for s in m["scenarios"]:
        if wanted is None or s["n"] == wanted:
            show_scenario(m, s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
