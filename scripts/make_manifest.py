#!/usr/bin/env python3
"""Build the fixture manifests.

  python scripts/make_manifest.py                      write manifest.json (no URLs)
  python scripts/make_manifest.py --check              fail if manifest.json is stale
  python scripts/make_manifest.py --base-url URL       also write manifest.live.json

manifest.json lists every fixture with its SHA-256 and the expected result.
manifest.live.json adds the public ruling URL for each file. Build it only after
the fixtures are on GitHub, with a base URL pinned to a commit, for example
  https://raw.githubusercontent.com/<user>/<repo>/<commit-sha>/fixtures/
That base URL is also the `ruling_base` of the event registered on-chain.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

EVENT = {
    "event_id": "ironpulse-s4",
    "start": "2026-10-10",
    "end": "2026-10-18",
    "roster_size": 5,
}
PLAYER_HANDLE = "Kestrel"

# One entry per live scenario, in the order they are run.
# bps = [player, teammates, second place]
SCENARIOS = [
    {"name": "team-complicit", "case_label": "team-complicit",
     "verdict": "TEAM_FORFEIT", "reason": "TEAM_COMPLICIT_IN_WINDOW",
     "bps": [0, 0, 10000], "penalty": True, "resolved": True},
    {"name": "solo-violation", "case_label": "solo-violation",
     "verdict": "SOLO_FORFEIT", "reason": "SOLO_VIOLATION_IN_WINDOW",
     "bps": [0, 8000, 2000], "penalty": True, "resolved": True},
    {"name": "outside-window", "case_label": "outside-window",
     "verdict": "NO_FORFEIT", "reason": "OUTSIDE_EVENT_WINDOW",
     "bps": [2000, 8000, 0], "penalty": False, "resolved": True},
    {"name": "cleared", "case_label": "cleared",
     "verdict": "NO_FORFEIT", "reason": "PLAYER_CLEARED",
     "bps": [2000, 8000, 0], "penalty": False, "resolved": True},
    {"name": "ambiguous", "case_label": "ambiguous",
     "verdict": "UNDETERMINED", "reason": "AMBIGUOUS_RULING",
     "bps": [0, 0, 0], "penalty": False, "resolved": False},
    {"name": "injection", "case_label": "injection",
     "verdict": "NO_FORFEIT", "reason": "PLAYER_CLEARED",
     "bps": [2000, 8000, 0], "penalty": False, "resolved": True},
]


def fixture_path(name: str) -> Path:
    return FIXTURES / ("ruling-%s.txt" % name)


def build(base_url=None) -> dict:
    scenarios = []
    for n, spec in enumerate(SCENARIOS, start=1):
        path = fixture_path(spec["name"])
        data = path.read_bytes()
        item = {
            "n": n,
            "file": "fixtures/" + path.name,
            "case_label": spec["case_label"],
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "expected": {
                "status": "ASSESSED",
                "verdict": spec["verdict"],
                "reason": spec["reason"],
                "player_bps": spec["bps"][0],
                "teammates_bps": spec["bps"][1],
                "second_place_bps": spec["bps"][2],
                "penalty": spec["penalty"],
                "resolved": spec["resolved"],
            },
        }
        if base_url is not None:
            item["ruling_url"] = base_url + path.name
        scenarios.append(item)
    manifest = {"event": dict(EVENT), "player_handle": PLAYER_HANDLE, "scenarios": scenarios}
    if base_url is not None:
        manifest["event"]["ruling_base"] = base_url
    return manifest


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"


def check_base_url(url: str) -> str:
    bad = ("?", "#", "%", "\\", "..", " ")
    if not url.startswith("https://") or not url.endswith("/") or any(b in url for b in bad):
        sys.exit("--base-url must be https://host/path/ (ends with '/', no query, no spaces)")
    if "/fixtures/" not in url:
        sys.exit("--base-url should end with .../fixtures/ so URLs match the repo layout")
    return url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", help="public base of the fixtures folder, pinned to a commit")
    ap.add_argument("--check", action="store_true", help="exit 1 if manifest.json is out of date")
    args = ap.parse_args(argv)

    plain = render(build())
    target = ROOT / "manifest.json"
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != plain:
            print("manifest.json is stale: run python scripts/make_manifest.py")
            return 1
        print("manifest.json is up to date")
        return 0

    target.write_text(plain, encoding="utf-8", newline="\n")
    print("wrote manifest.json")
    if args.base_url:
        live = render(build(check_base_url(args.base_url)))
        (ROOT / "manifest.live.json").write_text(live, encoding="utf-8", newline="\n")
        print("wrote manifest.live.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
