#!/usr/bin/env python3
"""
Utility to sync school and niche data for ALL schools found in team_pivot.csv.

What it does:
- Reads exports/team_pivot.csv (default path) to gather the set of team names.
- Merges into report_builder/config/schools.json: adds missing schools with
  basic placeholders (conference/tier/offense_type defaulted, lat/lon empty).
- Merges into report_builder/config/niche_data.json: adds missing schools with
  placeholder grades and summary strings for future editing.

Usage:
    python report_builder/scripts/update_school_data.py \
        --team-pivot exports/team_pivot.csv \
        --schools-json report_builder/config/schools.json \
        --niche-json report_builder/config/niche_data.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

DEFAULT_SCHOOLS_JSON = Path(__file__).resolve().parents[1] / "config" / "schools.json"
DEFAULT_NICHE_JSON = Path(__file__).resolve().parents[1] / "config" / "niche_data.json"
DEFAULT_TEAMS_JSON = Path(__file__).resolve().parents[2] / "settings" / "teams.json"
DEFAULT_GUIDE_DEFAULTS_YML = Path(__file__).resolve().parents[1] / "config" / "guide.defaults.yml"


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def parse_args():
    p = argparse.ArgumentParser(description="Update schools/niche data from settings/teams.json")
    p.add_argument("--teams-json", type=Path, default=DEFAULT_TEAMS_JSON)
    p.add_argument("--schools-json", type=Path, default=DEFAULT_SCHOOLS_JSON)
    p.add_argument("--niche-json", type=Path, default=DEFAULT_NICHE_JSON)
    p.add_argument("--guide-defaults", type=Path, default=DEFAULT_GUIDE_DEFAULTS_YML)
    return p.parse_args()


def ensure_school_entry(school_name: str, schools: list[dict]):
    for s in schools:
        if s.get("name") == school_name:
            return s
    # Create placeholder
    entry = {
        "name": school_name,
        "short": school_name,
        "city_state": "",
        "conference": "",
        "tier": "B",
        "offense_type": "",
        "lat": None,
        "lon": None,
        "notes": "",
    }
    schools.append(entry)
    return entry


def ensure_niche_entry(school_name: str, niche: dict):
    if school_name in niche:
        return
    niche[school_name] = {
        "overall_grade": "B",
        "academics_grade": "B",
        "value_grade": "B",
        "summary": "",
        "review_pos": "",
        "review_neg": "",
    }


def ensure_guide_defaults_entry(school_name: str, guide_cfg: dict):
    """
    Ensure guide.defaults.yml has placeholder entries for the school across:
    - risk_watchouts: "" (so editors can fill later)
    - politics_label_overrides: "" (keeps merge semantics simple)
    - airport_info: {airport_name, airport_code, airport_drive_time, notes_from_indy}
    - team_name_aliases: identical to school name by default
    """
    def _set_if_missing(dct, key, default):
        if not dct.get(key):
            dct[key] = default

    risk = guide_cfg.setdefault("risk_watchouts", {})
    _set_if_missing(risk, school_name, "TBD — add program-specific risk/watchouts.")

    politics = guide_cfg.setdefault("politics_label_overrides", {})
    _set_if_missing(politics, school_name, "Unknown")

    airport = guide_cfg.setdefault("airport_info", {})
    entry = airport.setdefault(
        school_name,
        {
            "airport_name": "Unknown",
            "airport_code": "UNK",
            "airport_drive_time": "Unknown",
            "notes_from_indy": "TBD — add common routing from IND and drive time from airport to campus.",
        },
    )
    # Fill any missing subfields on existing entries
    entry.setdefault("airport_name", "Unknown")
    entry.setdefault("airport_code", "UNK")
    entry.setdefault("airport_drive_time", "Unknown")
    entry.setdefault("notes_from_indy", "TBD — add common routing from IND and drive time from airport to campus.")

    aliases = guide_cfg.setdefault("team_name_aliases", {})
    _set_if_missing(aliases, school_name, school_name)


def main():
    args = parse_args()
    if not args.teams_json.exists():
        raise FileNotFoundError(f"teams.json not found at {args.teams_json}")

    teams_data = load_json(args.teams_json, default=[])
    teams = sorted({t.get("team") or t for t in teams_data if t})

    schools = load_json(args.schools_json, default=[])
    niche = load_json(args.niche_json, default={})
    guide_cfg = {}
    if args.guide_defaults.exists():
        with open(args.guide_defaults, "r", encoding="utf-8") as f:
            guide_cfg = yaml.safe_load(f) or {}

    for team in teams:
        ensure_school_entry(team, schools)
        ensure_niche_entry(team, niche)
        ensure_guide_defaults_entry(team, guide_cfg)

    save_json(args.schools_json, schools)
    save_json(args.niche_json, niche)
    # Save guide.defaults.yml back
    with open(args.guide_defaults, "w", encoding="utf-8") as f:
        yaml.safe_dump(guide_cfg, f, sort_keys=False, width=100)

    print(
        f"Updated {args.schools_json}, {args.niche_json}, and {args.guide_defaults} with {len(teams)} schools."
    )


if __name__ == "__main__":
    main()
