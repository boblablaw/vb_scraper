#!/usr/bin/env python3
"""
Merge NCAA WVB stats and rosters into a combined CSV.

 - Takes all roster columns.
 - Merges in stat columns from the stats CSV.
 - Joins on TeamID + PlayerID (preferred) or TeamID + Player name (fallback).
"""

import argparse
from pathlib import Path
import pandas as pd
import json
import re

# Root paths for matching photos and teams metadata
ROOT_DIR = Path(__file__).resolve().parents[1]
TEAMS_JSON = ROOT_DIR / "settings" / "teams.json"
PLAYER_PHOTOS_DIR = ROOT_DIR / "assets" / "player_photos"
SCHOOL_LOOKUP: dict[str, str] = {}

def merge_files(stats_path: Path, roster_path: Path, output_path: Path) -> None:
    global SCHOOL_LOOKUP
    if TEAMS_JSON.exists() and not SCHOOL_LOOKUP:
        try:
            teams = json.loads(TEAMS_JSON.read_text())
            for t in teams:
                name = t.get("team") or t.get("short_name") or ""
                for alias in [t.get("team")] + (t.get("team_name_aliases") or []) + [t.get("short_name") or ""]:
                    if alias:
                        SCHOOL_LOOKUP[alias.lower()] = name
        except Exception:
            SCHOOL_LOOKUP = {}

    stats = pd.read_csv(stats_path, dtype={"TeamID": str, "PlayerID": str})
    rosters = pd.read_csv(roster_path, dtype={"TeamID": str, "PlayerID": str})

    # Identify stat columns that are not in roster (avoid overwriting roster fields)
    roster_cols = set(rosters.columns)
    stat_cols = [
        c for c in stats.columns
        if c not in roster_cols
        and not c.endswith("_roster")
        and c != "Trpl Dbl"
    ]

    # Primary merge on TeamID + PlayerID when available
    merged_primary = rosters.merge(
        stats[["TeamID", "PlayerID"] + stat_cols],
        how="left",
        on=["TeamID", "PlayerID"],
        suffixes=("", "_stat"),
    )

    # Secondary merge on TeamID + Player (name) for rows still missing stats
    merged_secondary = rosters.merge(
        stats[["TeamID", "Player"] + stat_cols],
        how="left",
        on=["TeamID", "Player"],
        suffixes=("", "_stat"),
    )

    # Combine: prefer primary stats when present, else secondary
    def pick_stats(primary_row, secondary_row):
        if not primary_row.isna().all():
            return primary_row
        return secondary_row

    combined_stats = merged_primary[stat_cols].combine(
        merged_secondary[stat_cols],
        func=lambda p, s: pick_stats(p, s),
    )

    merged = rosters.copy()
    # Add School column based on teams.json lookup (fall back to Team)
    def school_name(team_val: str) -> str:
        if not team_val:
            return ""
        val = str(team_val)
        return SCHOOL_LOOKUP.get(val.lower(), val)

    # Insert School to the left of Team if possible
    if "Team" in merged.columns:
        team_idx = merged.columns.get_loc("Team")
        merged.insert(team_idx, "School", merged["Team"].apply(school_name))
    else:
        merged.insert(0, "School", merged.apply(lambda r: school_name(r.get("team") or ""), axis=1))

    for col in stat_cols:
        merged[col] = combined_stats[col]

    # Attach player photo filename if found: pattern <team>_<player>.jpg
    photo_index = None
    merged["player_photo"] = ""

    if PLAYER_PHOTOS_DIR.exists():
        # Index photos (any common extension)
        photo_index: dict[str, str] = {}
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"):
            for p in PLAYER_PHOTOS_DIR.glob(ext):
                photo_index[p.name.lower()] = p.name

        # Load team aliases and canonical slugs from teams.json
        team_aliases: dict[str, str] = {}
        if TEAMS_JSON.exists():
            try:
                teams = json.loads(TEAMS_JSON.read_text())
                for t in teams:
                    canonical = t.get("team") or t.get("short_name") or ""
                    canonical_slug = re.sub(r"[^A-Za-z0-9]+", "_", canonical).strip("_")
                    aliases = t.get("team_name_aliases") or []
                    for alias in [canonical] + aliases:
                        if alias:
                            team_aliases[alias.lower()] = canonical_slug
            except Exception:
                team_aliases = {}

        def _slugify(s: str) -> str:
            s = re.sub(r"[^A-Za-z0-9]+", "_", s)
            s = re.sub(r"_+", "_", s).strip("_")
            return s

        def find_photo(team: str, player: str) -> str:
            if not photo_index:
                return ""
            # Use school/team field first, fall back to team alias
            team_lookup = team_aliases.get(team.lower(), team)
            team_key = _slugify(team_lookup)
            player_key = _slugify(player)
            if not team_key or not player_key:
                return ""

            base = f"{team_key}_{player_key}".lower()
            for ext in (".jpg", ".jpeg", ".png"):
                fname = base + ext
                if fname in photo_index:
                    return photo_index[fname]

            # Also try with common suffixes/prefixes: if team_key missing University, append it
            for suffix in ("_university", "_college"):
                fname = (team_key + suffix + f"_{player_key}").lower() + ".png"
                if fname in photo_index:
                    return photo_index[fname]
                fname = (team_key + suffix + f"_{player_key}").lower() + ".jpg"
                if fname in photo_index:
                    return photo_index[fname]

            # Loose contains match
            for fname, original in photo_index.items():
                if team_key in fname and player_key in fname:
                    return original
            return ""

        merged["player_photo"] = merged.apply(
            lambda row: find_photo(
                str(row.get("School") or row.get("Team") or row.get("team") or ""),
                str(row.get("Player") or ""),
            ),
            axis=1,
        )

    merged.to_csv(output_path, index=False)
    print(f"Wrote merged file with {len(merged)} rows to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Merge NCAA WVB stats and rosters into a combined CSV.")
    parser.add_argument("--stats", required=True, type=Path, help="Path to stats CSV (e.g., ncaa_wvb_player_stats_d1_2025.csv)")
    parser.add_argument("--rosters", required=True, type=Path, help="Path to roster CSV (e.g., ncaa_wvb_rosters_d1_2025.csv)")
    parser.add_argument("--output", required=True, type=Path, help="Path to write merged CSV")
    args = parser.parse_args()

    merge_files(args.stats, args.rosters, args.output)


if __name__ == "__main__":
    main()
