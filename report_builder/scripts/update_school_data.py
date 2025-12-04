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

DEFAULT_SCHOOLS_JSON = Path(__file__).resolve().parents[1] / "config" / "schools.json"
DEFAULT_NICHE_JSON = Path(__file__).resolve().parents[1] / "config" / "niche_data.json"
DEFAULT_TEAMS_JSON = Path(__file__).resolve().parents[2] / "settings" / "teams.json"


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
        "offense_type": "5-1",
        "lat": None,
        "lon": None,
        "vb_opp_score": 2.0,
        "geo_score": 2.0,
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


def main():
    args = parse_args()
    if not args.teams_json.exists():
        raise FileNotFoundError(f"teams.json not found at {args.teams_json}")

    teams_data = load_json(args.teams_json, default=[])
    teams = sorted({t.get("name") or t.get("team") or t for t in teams_data if t})

    schools = load_json(args.schools_json, default=[])
    niche = load_json(args.niche_json, default={})

    for team in teams:
        ensure_school_entry(team, schools)
        ensure_niche_entry(team, niche)

    save_json(args.schools_json, schools)
    save_json(args.niche_json, niche)
    print(f"Updated {args.schools_json} and {args.niche_json} with {len(teams)} schools.")


if __name__ == "__main__":
    main()
