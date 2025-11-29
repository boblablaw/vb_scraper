#!/usr/bin/env python3
"""
Compare export coverage against the full TEAMS list from settings.

Identifies teams with no roster data in the export.
"""

import sys
from pathlib import Path

import pandas as pd

# Append parent to sys.path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings import TEAMS
from utils import normalize_school_key

# Import from validation script
sys.path.insert(0, str(Path(__file__).parent))
from validate_exports import latest_export, load_export


def main():
    # Load export
    fn = latest_export()
    print(f"Loading: {fn}")
    df = load_export(fn)

    # Get unique teams in export (normalized)
    export_teams_raw = df["Team"].dropna().unique()
    export_teams_normalized = {normalize_school_key(t): t for t in export_teams_raw}

    # Get all teams from settings (normalized)
    settings_teams = []
    for team_info in TEAMS:
        team_name = team_info["team"]
        normalized = normalize_school_key(team_name)
        settings_teams.append({
            "team": team_name,
            "normalized": normalized,
            "conference": team_info["conference"],
            "url": team_info["url"],
            "stats_url": team_info["stats_url"],
        })

    # Find missing teams
    missing = [t for t in settings_teams if t["normalized"] not in export_teams_normalized]

    # Write results
    missing_df = pd.DataFrame(missing)
    output_file = "exports/missing_teams.tsv"
    missing_df.to_csv(output_file, sep="\t", index=False)

    print(f"\nTotal teams in settings: {len(settings_teams)}")
    print(f"Teams in export: {len(export_teams_normalized)}")
    print(f"Missing teams: {len(missing)}")
    print(f"\nWrote: {output_file}")

    if missing:
        print("\nMissing teams by conference:")
        by_conf = missing_df.groupby("conference").size().sort_values(ascending=False)
        for conf, count in by_conf.items():
            print(f"  {conf}: {count}")


if __name__ == "__main__":
    main()
