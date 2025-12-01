# run_scraper.py
from __future__ import annotations

import argparse
import csv
import logging
import time
import os
from typing import Any, Dict, List

from settings import TEAMS
from scraper.rpi_lookup import build_rpi_lookup
from scraper.team_analysis import analyze_team
from logging_utils import setup_logging, get_logger


REQUEST_DELAY = 1.0

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(EXPORT_DIR, "d1_rosters_2025_with_stats_and_incoming.csv")

LOG_FILE = os.path.join(EXPORT_DIR, "scraper.log")

# Configure logging as soon as the module is imported
setup_logging(
    level=logging.INFO,   # or logging.DEBUG
    log_file=LOG_FILE,
)

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="Scrape D1 Women's Volleyball rosters with optional team filtering"
    )
    parser.add_argument(
        "--team",
        action="append",
        dest="teams",
        help="Team name to scrape (can be used multiple times). Example: --team 'Brigham Young University'"
    )
    parser.add_argument(
        "--teams-file",
        type=str,
        help="File containing team names (one per line) to scrape"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file base name (without extension). Default: d1_rosters_2025_with_stats_and_incoming"
    )
    args = parser.parse_args()
    
    # Determine output file path
    output_base = args.output if args.output else "d1_rosters_2025_with_stats_and_incoming"
    output_csv = os.path.join(EXPORT_DIR, f"{output_base}.csv")
    
    # Determine which teams to scrape
    teams_to_scrape = TEAMS
    
    if args.teams or args.teams_file:
        # Collect team names from arguments
        selected_team_names = set(args.teams or [])
        
        # Add teams from file if provided
        if args.teams_file:
            if os.path.exists(args.teams_file):
                with open(args.teams_file, 'r') as f:
                    for line in f:
                        team_name = line.strip()
                        if team_name:
                            selected_team_names.add(team_name)
            else:
                logger.error(f"Teams file not found: {args.teams_file}")
                return
        
        # Filter TEAMS list
        teams_to_scrape = [t for t in TEAMS if t['team'] in selected_team_names]
        
        if not teams_to_scrape:
            logger.error("No matching teams found. Check team names.")
            return
        
        logger.info(f"Filtering to {len(teams_to_scrape)} team(s): {[t['team'] for t in teams_to_scrape]}")
    
    all_rows: List[Dict[str, Any]] = []

    # Initialize filtered staff players log
    filtered_log_path = os.path.join(EXPORT_DIR, "filtered_staff_players.txt")
    with open(filtered_log_path, "w", encoding="utf-8") as f:
        f.write("# Filtered non-player entries (likely staff)\n")
        f.write("# Format: Team\tName\tPosition\n")
        f.write("#" + "="*80 + "\n")

    logger.info("Building RPI lookup...")
    rpi_lookup = build_rpi_lookup()

    for team_info in teams_to_scrape:
        rows = analyze_team(team_info, rpi_lookup)
        all_rows.extend(rows)
        time.sleep(REQUEST_DELAY)

    if not all_rows:
        logger.warning("No rows generated, nothing to write.")
        return
    
    # Calculate derived stats if not already present
    for row in all_rows:
        # Calculate D/S (Digs per Set) if we have digs and sets_played
        if row.get("digs_per_set") in ("", None):
            digs = row.get("digs")
            sets = row.get("sets_played")
            if digs not in ("", None) and sets not in ("", None):
                try:
                    d = float(digs)
                    s = float(sets)
                    if s > 0:
                        row["digs_per_set"] = round(d / s, 2)
                except:
                    pass
        
        # Calculate Rec% (Reception Percentage) if we have TRE and RE
        if row.get("reception_pct") in ("", None):
            tre = row.get("total_reception_attempts")
            re = row.get("reception_errors")
            if tre not in ("", None) and re not in ("", None):
                try:
                    total = float(tre)
                    errors = float(re)
                    if total > 0:
                        row["reception_pct"] = round((total - errors) / total, 3)
                except:
                    pass

    # Simplified column set - only roster + stats data
    base_fields = [
        "team",
        "conference",
        "rank",
        "record",
        "name",
        "position",
        "class",
        "height",
        
        # Stats fields
        "matches_started",
        "matches_played",
        "sets_played",
        "points",
        "points_per_set",
        "kills",
        "kills_per_set",
        "attack_errors",
        "total_attacks",
        "hitting_pct",
        "assists",
        "assists_per_set",
        "aces",
        "aces_per_set",
        "service_errors",
        "digs",
        "digs_per_set",
        "reception_errors",
        "total_reception_attempts",
        "reception_pct",
        "block_solos",
        "block_assists",
        "total_blocks",
        "blocks_per_set",
        "ball_handling_errors",
    ]
    
    # Columns to explicitly exclude (duplicates from defensive stats merge)
    exclude_columns = {
        "number", "number_def",
        "bio link", "bio link_def",
        "sets_played_def",
        "dig/s",  # Use digs_per_set instead
        "rec%",  # Use reception_pct instead
        "re/s", "be",
        "total_attacks_def",
    }

    # Collect any extra stat fields that weren't in base_fields
    extra_fields: List[str] = []
    seen = set(base_fields) | exclude_columns

    for r in all_rows:
        for k in r.keys():
            if k not in seen and k not in exclude_columns:
                seen.add(k)
                extra_fields.append(k)

    fieldnames = base_fields + extra_fields

    # Create friendly headers with abbreviations
    friendly_headers = {
        "team": "Team",
        "conference": "Conference",
        "rank": "Rank",
        "record": "Record",
        "name": "Name",
        "position": "Position",
        "class": "Class",
        "height": "Height",
        "matches_started": "MS",
        "matches_played": "MP",
        "sets_played": "SP",
        "points": "PTS",
        "points_per_set": "PTS/S",
        "kills": "K",
        "kills_per_set": "K/S",
        "attack_errors": "AE",
        "total_attacks": "TA",
        "hitting_pct": "HIT%",
        "assists": "A",
        "assists_per_set": "A/S",
        "aces": "SA",
        "aces_per_set": "SA/S",
        "service_errors": "SE",
        "digs": "D",
        "digs_per_set": "D/S",
        "reception_errors": "RE",
        "total_reception_attempts": "TRE",
        "reception_pct": "Rec%",
        "block_solos": "BS",
        "block_assists": "BA",
        "total_blocks": "TB",
        "blocks_per_set": "B/S",
        "ball_handling_errors": "BHE",
    }

    friendly_fieldnames = [friendly_headers.get(f, f) for f in fieldnames]

    # ---- WRITE CSV (friendly headers, no Excel protections) ----
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=friendly_fieldnames)
        writer.writeheader()

        for r in all_rows:
            out_row = {
                friendly_headers.get(k, k): r.get(k, "")
                for k in fieldnames
            }
            writer.writerow(out_row)

    logger.info("Wrote %d player rows to: %s", len(all_rows), output_csv)
    logger.debug("Columns written: %s", friendly_fieldnames)


if __name__ == "__main__":
    main()
