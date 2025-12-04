"""
Geocode missing latitude/longitude values in settings/teams.json using
OpenStreetMap's Nominatim service (public endpoint).

Usage:
  python scripts/geocode_teams.py [--delay 1.1] [--force-all] [--fill-city-state] [--limit 0] [--dry-run]

Options:
  --delay <seconds>   Seconds to sleep between requests (default 1.1 to be gentle).
  --force-all         Geocode every team, not just those missing lat/lon.
  --fill-city-state   Populate `city_state`, `zip_code`, and `county` using geocoder results, even if lat/lon already exist.
  --limit <n>         Stop after processing N teams (0 = no limit; default 0).
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


def geocode(name: str) -> tuple[float | None, float | None, str | None, str | None, str | None]:
    params = {"q": name, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None, None, None, None, None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        address = data[0].get("address", {})
        city_state, zip_code, county = extract_address_bits(address)
        return lat, lon, city_state, zip_code, county
    except Exception:
        return None, None, None, None, None


def reverse_geocode(lat: float, lon: float) -> tuple[str | None, str | None, str | None]:
    params = {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1}
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get("https://nominatim.openstreetmap.org/reverse", params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json() or {}
        return extract_address_bits(data.get("address", {}) or {})
    except Exception:
        return None, None, None


def extract_address_bits(addr: dict) -> tuple[str | None, str | None, str | None]:
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("hamlet")
        or addr.get("municipality")
        or addr.get("locality")
        or addr.get("county")
    )
    state = addr.get("state") or addr.get("state_district")
    zip_code = addr.get("postcode")
    county = addr.get("county") or addr.get("region")
    if city and state:
        city_state = f"{city}, {state}"
    elif state:
        city_state = state
    else:
        city_state = None
    return city_state, zip_code, county


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.1, help="Seconds between requests (default 1.1)")
    parser.add_argument("--force-all", action="store_true", help="Geocode every team, not just missing coords")
    parser.add_argument("--fill-city-state", action="store_true", help="Populate city_state using geocoder results even when lat/lon exist")
    parser.add_argument("--limit", type=int, default=0, help="Max teams to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Print updates without writing file")
    args = parser.parse_args()

    teams = load_teams()
    updated = 0
    missing = 0
    city_updates = 0
    zip_updates = 0
    county_updates = 0

    for idx, t in enumerate(teams):
        if args.limit and (updated + city_updates + missing) >= args.limit:
            print(f"Reached limit {args.limit}; stopping.")
            break
        has_coords = t.get("lat") not in (None, "") and t.get("lon") not in (None, "")
        needs_coords = args.force_all or not has_coords
        needs_city = args.fill_city_state and not t.get("city_state")
        needs_zip = args.fill_city_state and not t.get("zip_code")
        needs_county = args.fill_city_state and not t.get("county")

        if not (needs_coords or needs_city or needs_zip or needs_county):
            continue

        query = t.get("team") or t.get("name")
        if not query:
            continue

        lat = lon = city_state = zip_code = county = None

        if needs_coords:
            lat, lon, city_state, zip_code, county = geocode(query)
        elif (needs_city or needs_zip or needs_county) and has_coords:
            city_state, zip_code, county = reverse_geocode(t["lat"], t["lon"])

        if needs_coords and (lat is None or lon is None):
            missing += 1
            print(f"[MISS] {query}")
        else:
            if needs_coords:
                updated += 1
                t["lat"] = lat
                t["lon"] = lon
                print(f"[OK]   {query} -> ({lat:.4f}, {lon:.4f})")
            if city_state and (needs_city or args.fill_city_state):
                t["city_state"] = city_state
                city_updates += 1
                if not needs_coords:
                    print(f"[CITY] {query} -> {city_state}")
            if zip_code and (needs_zip or args.fill_city_state):
                t["zip_code"] = zip_code
                zip_updates += 1
                if not needs_coords and not city_state:
                    print(f"[ZIP ] {query} -> {zip_code}")
            if county and (needs_county or args.fill_city_state):
                t["county"] = county
                county_updates += 1
                if not needs_coords and not city_state:
                    print(f"[COUNTY] {query} -> {county}")

        time.sleep(max(args.delay, 0))

    if args.dry_run:
        print(f"\nDry run: {updated} coord updates, {city_updates} city/state updates, {zip_updates} zip updates, {county_updates} county updates, {missing} misses. No file written.")
        return

    save_teams(teams)
    print(f"\nWrote {updated} coord updates, {city_updates} city/state updates, {zip_updates} zip updates, {county_updates} county updates to {TEAMS_PATH}. Misses: {missing}.")


if __name__ == "__main__":
    main()
