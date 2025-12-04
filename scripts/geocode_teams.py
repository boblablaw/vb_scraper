"""
Geocode missing latitude/longitude values in settings/teams.json using
OpenStreetMap's Nominatim service (public endpoint).

Usage:
  python scripts/geocode_teams.py [--delay 1.1] [--force-all] [--dry-run]

Options:
  --delay <seconds>   Seconds to sleep between requests (default 1.1 to be gentle).
  --force-all         Geocode every team, not just those missing lat/lon.
  --dry-run           Do not write changes; just print planned updates.

Notes:
  - Nominatim usage policy requires a descriptive User-Agent and reasonable rate limits.
  - Results are approximate; verify any critical coordinates before use.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parent.parent
TEAMS_PATH = ROOT / "settings" / "teams.json"
USER_AGENT = "vb-scraper/1.0 (contact: dev@local)"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def load_teams() -> List[Dict[str, Any]]:
    with open(TEAMS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_teams(data: List[Dict[str, Any]]):
    with open(TEAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def geocode(name: str) -> tuple[float | None, float | None]:
    params = {"q": name, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None, None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon
    except Exception:
        return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.1, help="Seconds between requests (default 1.1)")
    parser.add_argument("--force-all", action="store_true", help="Geocode every team, not just missing coords")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing file")
    args = parser.parse_args()

    teams = load_teams()
    updated = 0
    missing = 0

    for idx, t in enumerate(teams):
        needs = args.force_all or t.get("lat") in (None, "") or t.get("lon") in (None, "")
        if not needs:
            continue

        query = t.get("team") or t.get("name")
        if not query:
            continue

        lat, lon = geocode(query)
        if lat is None or lon is None:
            missing += 1
            print(f"[MISS] {query}")
        else:
            updated += 1
            t["lat"] = lat
            t["lon"] = lon
            print(f"[OK]   {query} -> ({lat:.4f}, {lon:.4f})")
        time.sleep(max(args.delay, 0))

    if args.dry_run:
        print(f"\nDry run: {updated} updates, {missing} misses. No file written.")
        return

    save_teams(teams)
    print(f"\nWrote {updated} updates to {TEAMS_PATH}. Misses: {missing}.")


if __name__ == "__main__":
    main()
