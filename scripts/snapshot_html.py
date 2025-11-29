#!/usr/bin/env python3
"""
Snapshot HTML from missing teams for offline parser development.

Usage:
    python scripts/snapshot_html.py --teams-file exports/missing_teams.tsv
    python scripts/snapshot_html.py --team "University of Wyoming"
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Append parent to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import fetch_html, normalize_school_key
from logging_utils import get_logger

logger = get_logger(__name__)

FIXTURES_DIR = "fixtures/html"
os.makedirs(FIXTURES_DIR, exist_ok=True)


def snapshot_team(team_name, url, force=False):
    """Download and save HTML for a single team."""
    normalized = normalize_school_key(team_name)
    filename = f"{normalized}.html"
    filepath = os.path.join(FIXTURES_DIR, filename)
    
    if os.path.exists(filepath) and not force:
        logger.info("Skipping %s (already exists)", team_name)
        return False
    
    try:
        logger.info("Fetching: %s from %s", team_name, url)
        html = fetch_html(url)
        
        # Check if it's a JS redirect
        is_redirect = "window.location" in html and len(html) < 500
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        
        logger.info("Saved %s (%d bytes)%s", filename, len(html), " [JS REDIRECT]" if is_redirect else "")
        return True
        
    except Exception as e:
        logger.error("Failed to fetch %s: %s", team_name, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Snapshot HTML from team roster pages")
    parser.add_argument("--teams-file", help="TSV file with team info (from compare_export_to_teams.py)")
    parser.add_argument("--team", action="append", help="Specific team name(s) to snapshot")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--limit", type=int, default=30, help="Max teams to snapshot (default: 30)")
    args = parser.parse_args()
    
    teams_to_snapshot = []
    
    if args.teams_file:
        df = pd.read_csv(args.teams_file, sep="\t")
        for _, row in df.iterrows():
            teams_to_snapshot.append({
                "team": row["team"],
                "url": row["url"],
            })
    
    if args.team:
        # Would need to look up URLs from settings.TEAMS
        from settings import TEAMS
        for team_name in args.team:
            normalized = normalize_school_key(team_name)
            for t in TEAMS:
                if normalize_school_key(t["team"]) == normalized:
                    teams_to_snapshot.append({
                        "team": t["team"],
                        "url": t["url"],
                    })
                    break
    
    if not teams_to_snapshot:
        print("No teams specified. Use --teams-file or --team")
        return
    
    # Limit number of snapshots
    teams_to_snapshot = teams_to_snapshot[:args.limit]
    
    logger.info("Snapshotting %d team(s)", len(teams_to_snapshot))
    
    success = 0
    failed = 0
    skipped = 0
    
    for team_info in teams_to_snapshot:
        result = snapshot_team(team_info["team"], team_info["url"], force=args.force)
        if result:
            success += 1
        elif result is False:
            skipped += 1
        else:
            failed += 1
    
    logger.info("Complete: %d success, %d skipped, %d failed", success, skipped, failed)


if __name__ == "__main__":
    main()
