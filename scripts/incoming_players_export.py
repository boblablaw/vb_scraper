import csv
import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple, Optional

from incoming_players import get_incoming_players, normalize_school_key

D1_PROGRAMS_CSV = "d1_wvb_programs_base.csv"
OUTPUT_CSV = "incoming_players_d1_only.csv"
OUTPUT_JSON_FLAT = "incoming_players_d1_only.json"
OUTPUT_JSON_GROUPED = "incoming_players_d1_only_grouped.json"
OUTPUT_JSON_MISSING = "incoming_players_missing_schools.json"


def current_timestamp_iso() -> str:
    """
    Return current UTC time in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def load_d1_school_keys(teams_csv: str = D1_PROGRAMS_CSV) -> Set[str]:
    """
    Load normalized D1 school keys from the given CSV.
    Expects a 'school' column.
    """
    if not os.path.exists(teams_csv):
        print(f"[WARN] No {teams_csv} found — cannot load D1 schools.")
        return set()

    d1_keys: Set[str] = set()

    with open(teams_csv, newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        if "school" not in reader.fieldnames:
            print(f"[WARN] {teams_csv} missing 'school' column — cannot check.")
            return set()

        for row in reader:
            school = row.get("school")
            if school:
                d1_keys.add(normalize_school_key(school))

    return d1_keys


def cross_check_schools_against_d1(
    players: List[Dict[str, str]],
    teams_csv: str = D1_PROGRAMS_CSV,
) -> Tuple[List[Dict[str, str]], Dict[str, Set[str]]]:
    """
    Compare player schools against D1 list.

    Returns:
        valid_players: players whose normalized school matches D1.
        missing: {original_school_name: set(conferences)} for non-matches.
    """
    print("\n=============== D1 SCHOOL CHECK ===================")

    d1_keys = load_d1_school_keys(teams_csv)
    if not d1_keys:
        print("Skipping D1 check (no D1 school keys loaded).")
        print("===================================================\n")
        # If no D1 list, treat all as valid so you still get an export.
        return players, {}

    missing: Dict[str, Set[str]] = {}
    valid_players: List[Dict[str, str]] = []

    for p in players:
        school_raw = p.get("school", "").strip()
        conf = p.get("conference", "").strip()
        key = normalize_school_key(school_raw)

        if key in d1_keys:
            valid_players.append(p)
        else:
            missing.setdefault(school_raw, set()).add(conf)

    if not missing:
        print("All incoming schools match the D1 list.")
    else:
        print("Schools NOT found in D1 list:")
        for s, confs in sorted(missing.items(), key=lambda x: x[0].lower()):
            conf_str = ", ".join(sorted(confs))
            print(f"  {s}  (Conferences: {conf_str})")

    print("===================================================\n")
    return valid_players, missing


def export_players_to_csv(
    players: List[Dict[str, str]],
    out_csv: str = OUTPUT_CSV,
    fieldnames: Optional[List[str]] = None,
) -> None:
    """
    Export a list of player dicts to CSV.
    """
    if not players:
        print(f"[INFO] No players to export to {out_csv}.")
        return

    if fieldnames is None:
        fieldnames = list(players[0].keys())

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in players:
            writer.writerow(p)

    print(f"[OK] Exported {len(players)} players to {out_csv}")


def export_players_to_json_flat(
    players: List[Dict[str, str]],
    out_json: str = OUTPUT_JSON_FLAT,
) -> None:
    """
    Export list of valid players to a flat JSON structure:
    {
        "generated_at": "...",
        "count": N,
        "players": [ ... ]
    }
    """
    if not players:
        print(f"[INFO] No players to export to {out_json}.")
        return

    payload = {
        "generated_at": current_timestamp_iso(),
        "count": len(players),
        "players": players,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    print(f"[OK] Exported {len(players)} players to {out_json}")


def export_players_to_json_grouped(
    players: List[Dict[str, str]],
    out_json: str = OUTPUT_JSON_GROUPED,
) -> None:
    """
    Export players grouped in a nested structure:

    {
        "generated_at": "...",
        "by_conference": {
            "America East Conference": {
                "Bryant University": [ {player}, ... ],
                "Binghamton University": [ ... ],
                ...
            },
            ...
        },
        "by_school": {
            "Bryant University": [ {player}, ... ],
            "Binghamton University": [ ... ],
            ...
        }
    }
    """
    if not players:
        print(f"[INFO] No players to export to {out_json}.")
        return

    by_conference: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    by_school: Dict[str, List[Dict[str, str]]] = {}

    for p in players:
        conf = p.get("conference", "").strip() or "Unknown Conference"
        school = p.get("school", "").strip() or "Unknown School"

        # by_conference[conf][school] -> list of players
        if conf not in by_conference:
            by_conference[conf] = {}
        if school not in by_conference[conf]:
            by_conference[conf][school] = []
        by_conference[conf][school].append(p)

        # by_school[school] -> list of players
        if school not in by_school:
            by_school[school] = []
        by_school[school].append(p)

    payload = {
        "generated_at": current_timestamp_iso(),
        "by_conference": by_conference,
        "by_school": by_school,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    print(f"[OK] Exported grouped players JSON to {out_json}")


def export_missing_to_json(
    missing: Dict[str, Set[str]],
    out_json: str = OUTPUT_JSON_MISSING,
) -> None:
    """
    Export missing schools info to JSON:

    {
        "generated_at": "...",
        "missing_schools": [
            {
                "school": "Some School",
                "conferences": ["Conf A", "Conf B"],
                "normalized_key": "some school normalized"
            },
            ...
        ]
    }
    """
    if not missing:
        print(f"[INFO] No missing schools to export to {out_json}.")
        return

    missing_list = []
    for school, confs in sorted(missing.items(), key=lambda x: x[0].lower()):
        missing_list.append(
            {
                "school": school,
                "conferences": sorted(list(confs)),
                "normalized_key": normalize_school_key(school),
            }
        )

    payload = {
        "generated_at": current_timestamp_iso(),
        "missing_schools": missing_list,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    print(f"[OK] Exported missing schools JSON to {out_json}")


def main():
    # 1. Load incoming players from the raw-text-based script
    players = get_incoming_players()

    # 2. Cross-check against D1 schools using aliases + normalization
    valid_players, missing = cross_check_schools_against_d1(players)

    # 3. Export only valid D1 players (CSV + JSONs)
    export_players_to_csv(valid_players, out_csv=OUTPUT_CSV)
    export_players_to_json_flat(valid_players, out_json=OUTPUT_JSON_FLAT)
    export_players_to_json_grouped(valid_players, out_json=OUTPUT_JSON_GROUPED)

    # 4. Export missing school info if there is any
    export_missing_to_json(missing, out_json=OUTPUT_JSON_MISSING)

    # 5. Also log the schools that need alias tweaks to console
    if missing:
        print("\nYou may want to add/adjust aliases for these schools:")
        for s in sorted(missing.keys(), key=str.lower):
            print(f"  - {s}")


if __name__ == "__main__":
    main()