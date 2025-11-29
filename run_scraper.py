# run_scraper.py
from __future__ import annotations

import argparse
import csv
import logging
import time
import os
from typing import Any, Dict, List

from settings import TEAMS
from utils import excel_unprotect
from rpi_lookup import build_rpi_lookup
from team_analysis import analyze_team
from logging_utils import setup_logging, get_logger


REQUEST_DELAY = 1.0

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(EXPORT_DIR, "d1_rosters_2026_with_stats_and_incoming.csv")
OUTPUT_TSV = os.path.join(EXPORT_DIR, "d1_rosters_2026_with_stats_and_incoming.tsv")

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
    args = parser.parse_args()
    
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

    logger.info("Building RPI lookup...")
    rpi_lookup = build_rpi_lookup()

    for team_info in teams_to_scrape:
        rows = analyze_team(team_info, rpi_lookup)
        all_rows.extend(rows)
        time.sleep(REQUEST_DELAY)

    if not all_rows:
        logger.warning("No rows generated, nothing to write.")
        return

    base_fields = [
        "team",
        "conference",
        "roster_url",
        "stats_url",
        "team_rpi_rank",
        "team_overall_record",

        "name",
        "position_raw",
        "position",

        "class_raw",
        "class",
        "class_next_year",

        "height_raw",
        "height",

        "is_setter",
        "is_pin_hitter",
        "is_middle_blocker",
        "is_def_specialist",
        "is_graduating",
        "is_outgoing_transfer",
        "is_incoming_transfer",

        # 2026 SETTERS
        "returning_setter_count_2026",
        "returning_setter_names_2026",
        "incoming_setter_count_2026",
        "incoming_setter_names_2026",
        "projected_setter_count_2026",

        # 2026 PINS
        "returning_pin_hitter_count_2026",
        "returning_pin_hitter_names_2026",
        "incoming_pin_hitter_count_2026",
        "incoming_pin_hitter_names_2026",
        "projected_pin_hitter_count_2026",

        # 2026 MIDS
        "returning_middle_blocker_count_2026",
        "returning_middle_blocker_names_2026",
        "incoming_middle_blocker_count_2026",
        "incoming_middle_blocker_names_2026",
        "projected_middle_blocker_count_2026",

        # 2026 DS/L
        "returning_def_specialist_count_2026",
        "returning_def_specialist_names_2026",
        "incoming_def_specialist_count_2026",
        "incoming_def_specialist_names_2026",
        "projected_def_specialist_count_2026",

        # ---- PLAYING TIME / PARTICIPATION ----
        "sets_played",
        "matches_played",
        "matches_started",
        "games_played",
        "games_started",

        # ---- OFFENSIVE STATS ----
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

        # ---- DEFENSIVE STATS ----
        "digs",
        "digs_per_set",
        "reception_errors",
        "block_solos",
        "block_assists",
        "total_blocks",
        "blocks_per_set",
        "ball_handling_errors",
    ]

    coach_fields = [
        "coach1_name", "coach1_title", "coach1_email", "coach1_phone",
        "coach2_name", "coach2_title", "coach2_email", "coach2_phone",
        "coach3_name", "coach3_title", "coach3_email", "coach3_phone",
        "coach4_name", "coach4_title", "coach4_email", "coach4_phone",
        "coach5_name", "coach5_title", "coach5_email", "coach5_phone",
    ]

    extra_fields: List[str] = []
    seen = set(base_fields) | set(coach_fields)

    for r in all_rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                extra_fields.append(k)

    fieldnames_internal = base_fields + extra_fields + coach_fields

    friendly_aliases = {
        # Returning names
        "returning_setter_names_2026": "returning_setters",
        "returning_pin_hitter_names_2026": "returning_pins",
        "returning_middle_blocker_names_2026": "returning_middles",
        "returning_def_specialist_names_2026": "returning_defs",

        # Incoming names
        "incoming_setter_names_2026": "incoming_setters",
        "incoming_pin_hitter_names_2026": "incoming_pins",
        "incoming_middle_blocker_names_2026": "incoming_middles",
        "incoming_def_specialist_names_2026": "incoming_defs",
    }

    def beautify(col: str) -> str:
        base = " ".join(word.capitalize() for word in col.replace("_", " ").split())
        base = base.replace("2026", "").strip()
        base = " ".join(base.split())
        return base

    internal_to_friendly: Dict[str, str] = {}
    for col in fieldnames_internal:
        alias = friendly_aliases.get(col, col)
        internal_to_friendly[col] = beautify(alias)

    friendly_fieldnames = [internal_to_friendly[c] for c in fieldnames_internal]

    # ---- WRITE CSV (RAW VALUES, friendly headers) ----
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=friendly_fieldnames)
        writer.writeheader()

        for r in all_rows:
            raw_row = r.copy()

            raw_row["team_overall_record"] = excel_unprotect(
                raw_row.get("team_overall_record", "")
            )
            raw_row["height"] = excel_unprotect(raw_row.get("height", ""))

            for k in list(raw_row.keys()):
                if k.endswith("_phone"):
                    raw_row[k] = excel_unprotect(raw_row.get(k, ""))

            out_row = {
                internal_to_friendly[k]: raw_row.get(k, "")
                for k in fieldnames_internal
            }
            writer.writerow(out_row)

    # ---- WRITE TSV (SAFE VALUES, friendly headers) ----
    with open(OUTPUT_TSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=friendly_fieldnames, delimiter="\t")
        writer.writeheader()

        for r in all_rows:
            out_row = {
                internal_to_friendly[k]: r.get(k, "")
                for k in fieldnames_internal
            }
            writer.writerow(out_row)

    logger.info("Wrote %d player rows to: %s", len(all_rows), OUTPUT_CSV)
    logger.info("Also wrote TSV to: %s", OUTPUT_TSV)
    logger.debug("Columns written: %s", friendly_fieldnames)


if __name__ == "__main__":
    main()
