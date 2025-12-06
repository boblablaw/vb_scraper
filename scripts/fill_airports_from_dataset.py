from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional

# ---------- Paths ----------

ROOT = Path(__file__).resolve().parents[1]
TEAMS_JSON = ROOT / "settings" / "teams.json"
AIRPORTS_CSV = ROOT / "external_data" / "airports_us.csv"  # OurAirports US dataset


# ---------- Helpers ----------

def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points on Earth, in miles.
    """
    R_km = 6371.0
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_km = R_km * c
    return dist_km * 0.621371  # km -> miles


def load_airports() -> List[Dict[str, Any]]:
    """Load airports from OurAirports CSV and filter to major public airports
    (large/medium) with a valid 3-letter IATA code and scheduled commercial service.
    """
    airports: List[Dict[str, Any]] = []

    with AIRPORTS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # If you later switch to the global file, uncomment this:
            # if row.get("iso_country") != "US":
            #     continue

            t = row.get("type", "")
            # Only consider large and medium airports as "major" (likely commercial service)
            if t not in ("large_airport", "medium_airport"):
                continue

            # Skip airports without scheduled commercial service (filters out most
            # Air Force bases and other non-passenger facilities).
            scheduled = (row.get("scheduled_service") or "").strip().lower()
            if scheduled == "no":
                continue

            # Require a proper 3-letter alphabetic IATA code (skip local/FAA-only ids)
            iata = (row.get("iata_code") or "").strip().upper()
            if len(iata) != 3 or not iata.isalpha():
                continue

            name = (row.get("name") or "").strip()
            name_lower = name.lower()
            # Extra guard: skip obvious military fields even if they slip through
            # the scheduled_service filter.
            if "air force base" in name_lower or "army air" in name_lower:
                continue

            try:
                lat = float(row["latitude_deg"])
                lon = float(row["longitude_deg"])
            except (KeyError, ValueError, TypeError):
                continue

            airports.append(
                {
                    "name": name,
                    "code": iata,
                    "lat": lat,
                    "lon": lon,
                    "type": t,
                    "municipality": (row.get("municipality") or "").strip(),
                }
            )

    return airports


def find_nearest_airport(
    school_lat: float, school_lon: float, airports: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Find the closest airport by straight-line distance.
    Returns dict with added 'distance_mi'.
    """
    best: Optional[Dict[str, Any]] = None
    best_dist = float("inf")

    for ap in airports:
        d = haversine_miles(school_lat, school_lon, ap["lat"], ap["lon"])
        if d < best_dist:
            best_dist = d
            best = ap

    if best is None:
        return None

    best = dict(best)
    best["distance_mi"] = best_dist
    return best


def format_drive_time(distance_mi: float) -> str:
    """
    Very rough drive-time estimate assuming ~55 mph average speed.
    """
    if distance_mi <= 0:
        return ""

    hours = distance_mi / 55.0
    minutes = round(hours * 60)

    if minutes < 60:
        return f"~{minutes} min (~{round(distance_mi)} mi)"
    else:
        h = minutes // 60
        m = minutes % 60
        if m == 0:
            return f"~{h} hr (~{round(distance_mi)} mi)"
        return f"~{h} hr {m} min (~{round(distance_mi)} mi)"


# ---------- Main updater ----------

def main() -> None:
    # Load teams.json
    with TEAMS_JSON.open(encoding="utf-8") as f:
        teams = json.load(f)

    airports = load_airports()
    print(f"Loaded {len(airports)} airports from {AIRPORTS_CSV.name}")

    updated = 0

    for team in teams:
        lat = team.get("lat")
        lon = team.get("lon")

        # skip if no coordinates
        if lat is None or lon is None:
            continue

        # Skip teams with custom, hand-tuned airport info.
        # We only overwrite entries that look like they were auto-generated
        # by this script (with the standard "Nearest airport by straight-line distance" note).
        existing_notes = (team.get("airport_notes") or "").strip()
        if existing_notes:
            # Treat notes containing either of these phrases as auto-generated
            # and safe to overwrite. Anything else is considered hand-tuned.
            auto_markers = [
                "Nearest airport by straight-line distance",
                "Nearest major airport by straight-line distance",
            ]
            if not any(marker in existing_notes for marker in auto_markers):
                continue

        nearest = find_nearest_airport(float(lat), float(lon), airports)
        if not nearest:
            continue

        distance = nearest["distance_mi"]

        team["airport_name"] = nearest["name"]
        team["airport_code"] = nearest["code"]
        team["airport_drive_time"] = format_drive_time(distance)
        team["airport_notes"] = (
            f"Nearest major airport by straight-line distance (~{round(distance)} mi). "
            "Drive time is approximate; check routing for exact timing."
        )

        updated += 1
        print(
            f"[UPDATED] {team['team']}: {team['airport_name']} "
            f"({team['airport_code']}), ~{round(distance)} mi"
        )

    # Write back teams.json (pretty-printed)
    with TEAMS_JSON.open("w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Done. Updated {updated} teams.")


if __name__ == "__main__":
    main()
