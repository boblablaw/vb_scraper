# create_team_pivot_csv.py
# Reads simplified scraper output and calculates team-level aggregations
# including positional analysis, transfers, incoming players, coaches, and offense type.

import argparse
import csv
import re
import os
from typing import Any, Dict, List, Set

import pandas as pd

from settings.teams import TEAMS
from settings.transfers_config import OUTGOING_TRANSFERS
from scraper.utils import (
    normalize_school_key,
    normalize_player_name,
    normalize_class,
    class_next_year,
    is_graduating,
    extract_position_codes,
)
from scraper.coaches import find_coaches_page_url, parse_coaches_from_html, pack_coaches_for_row
from scraper.utils import fetch_html
from scraper.logging_utils import setup_logging, get_logger

logger = get_logger(__name__)

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

INPUT_CSV = os.path.join(EXPORT_DIR, "d1_rosters_2025_with_stats_and_incoming.csv")
OUTPUT_CSV = os.path.join(EXPORT_DIR, "d1_team_pivot_2025.csv")


def parse_incoming_players() -> List[Dict[str, str]]:
    """
    Parse incoming players from RAW_INCOMING_TEXT.
    Returns list of dicts with: name, school, position
    """
    from settings.incoming_players_data import RAW_INCOMING_TEXT
    
    players = []
    current_conf = ""
    
    for line in RAW_INCOMING_TEXT.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        
        # Conference header ends with ":"
        if line.endswith(":"):
            current_conf = line[:-1].strip()
            continue
        
        # Player line format: Name - School - Position (Club)
        # Or: Name - School - Position
        if " - " not in line:
            continue
        
        parts = line.split(" - ")
        if len(parts) < 3:
            continue
        
        name = parts[0].strip()
        school = parts[1].strip()
        position = parts[2].strip()
        
        # Remove club info from position if present
        if "(" in position:
            position = position.split("(")[0].strip()
        
        players.append({
            "name": normalize_player_name(name),
            "school": school,
            "position": position,
        })
    
    return players


def get_team_info(team_name: str) -> Dict[str, Any]:
    """Get team info from settings.TEAMS."""
    team_key = normalize_school_key(team_name)
    for t in TEAMS:
        if normalize_school_key(t["team"]) == team_key:
            return t
    return {}


def height_to_inches(height_str: str) -> float:
    """Convert '6-2' to inches (74.0)."""
    if not height_str or height_str == "":
        return float("nan")
    
    if "-" not in height_str:
        return float("nan")
    
    try:
        parts = height_str.split("-")
        feet = int(parts[0])
        inches = int(parts[1])
        return feet * 12 + inches
    except:
        return float("nan")


def inches_to_height(inches: float) -> str:
    """Convert inches to '6' 2\"' format."""
    if pd.isna(inches):
        return ""
    inches = int(round(inches))
    feet = inches // 12
    rem = inches % 12
    return f"{feet}' {rem}\""


def to_int_safe(val: Any) -> int:
    """Safely convert to int, return 0 if fails."""
    try:
        return int(float(val))
    except:
        return 0


def main(input_csv=None, output_csv=None):
    input_csv = input_csv or INPUT_CSV
    output_csv = output_csv or OUTPUT_CSV
    
    logger.info("Reading simplified scraper output: %s", input_csv)
    
    # Read the simplified CSV
    df = pd.read_csv(input_csv)
    
    # Normalize column names (friendly headers -> internal)
    col_map = {
        "Team": "team",
        "Conference": "conference",
        "Rank": "rank",
        "Record": "record",
        "Name": "name",
        "Position": "position",
        "Class": "class",
        "Height": "height",
        "MS": "matches_started",
        "MP": "matches_played",
        "SP": "sets_played",
        "PTS": "points",
        "PTS/S": "points_per_set",
        "K": "kills",
        "K/S": "kills_per_set",
        "AE": "attack_errors",
        "TA": "total_attacks",
        "HIT%": "hitting_pct",
        "A": "assists",
        "A/S": "assists_per_set",
        "SA": "aces",
        "SA/S": "aces_per_set",
        "SE": "service_errors",
        "D": "digs",
        "D/S": "digs_per_set",
        "RE": "reception_errors",
        "BS": "block_solos",
        "BA": "block_assists",
        "TB": "total_blocks",
        "B/S": "blocks_per_set",
        "BHE": "ball_handling_errors",
        "Rec%": "reception_pct",
    }
    df = df.rename(columns=col_map)
    
    # Parse incoming players
    logger.info("Parsing incoming players...")
    incoming_players = parse_incoming_players()
    
    # Build transfer lookups
    outgoing_by_team = {}
    incoming_by_team = {}
    
    for xfer in OUTGOING_TRANSFERS:
        old_team_key = normalize_school_key(xfer["old_team"])
        new_team_key = normalize_school_key(xfer["new_team"])
        
        if old_team_key not in outgoing_by_team:
            outgoing_by_team[old_team_key] = []
        outgoing_by_team[old_team_key].append(xfer)
        
        if new_team_key not in incoming_by_team:
            incoming_by_team[new_team_key] = []
        incoming_by_team[new_team_key].append(xfer)
    
    # Process each team
    results = []
    
    for team_name, team_df in df.groupby("team"):
        logger.info("Processing team: %s", team_name)
        team_key = normalize_school_key(team_name)
        team_info = get_team_info(team_name)
        
        # Get team metadata
        conference = team_df["conference"].iloc[0] if "conference" in team_df.columns else ""
        rank = team_df["rank"].iloc[0] if "rank" in team_df.columns else ""
        record = team_df["record"].iloc[0] if "record" in team_df.columns else ""
        roster_url = team_info.get("url", "")
        stats_url = team_info.get("stats_url", "")
        
        # Calculate positional flags for each player
        players_data = []
        for _, row in team_df.iterrows():
            position_raw = str(row.get("position", ""))
            pos_codes = extract_position_codes(position_raw)
            
            # S/DS doesn't count as setter
            is_setter = ("S" in pos_codes) and ("DS" not in pos_codes)
            is_pin = ("OH" in pos_codes) or ("RS" in pos_codes)
            is_middle = "MB" in pos_codes
            is_def = "DS" in pos_codes
            
            class_str = str(row.get("class", ""))
            class_norm = normalize_class(class_str)
            is_grad = is_graduating(class_norm)
            class_next = class_next_year(class_norm)
            
            # Check if outgoing transfer
            player_name = str(row.get("name", ""))
            is_outgoing = False
            for xfer in outgoing_by_team.get(team_key, []):
                if normalize_player_name(xfer["name"]) == normalize_player_name(player_name):
                    is_outgoing = True
                    break
            
            players_data.append({
                "name": player_name,
                "position_raw": position_raw,
                "pos_codes": pos_codes,
                "is_setter": is_setter,
                "is_pin": is_pin,
                "is_middle": is_middle,
                "is_def": is_def,
                "class": class_norm,
                "class_next": class_next,
                "is_graduating": is_grad,
                "is_outgoing_transfer": is_outgoing,
                "height": str(row.get("height", "")),
                "assists": to_int_safe(row.get("assists", 0)),
                "kills": to_int_safe(row.get("kills", 0)),
                "digs": to_int_safe(row.get("digs", 0)),
            })
        
        # Calculate returning players (not graduating, not outgoing transfer)
        returning_players = [p for p in players_data if not p["is_graduating"] and not p["is_outgoing_transfer"]]
        
        # Returning by position
        ret_setters = [p for p in returning_players if p["is_setter"]]
        ret_pins = [p for p in returning_players if p["is_pin"]]
        ret_middles = [p for p in returning_players if p["is_middle"]]
        ret_defs = [p for p in returning_players if p["is_def"]]
        
        # Format returning player names with class and primary stat
        def format_returning(players, stat_key):
            parts = []
            for p in players:
                stat_val = p.get(stat_key, 0)
                parts.append(f"{p['name']} - {p['class_next']} ({stat_val})")
            return ", ".join(parts)
        
        ret_setter_names = format_returning(ret_setters, "assists")
        ret_pin_names = format_returning(ret_pins, "kills")
        ret_middle_names = format_returning(ret_middles, "kills")
        ret_def_names = format_returning(ret_defs, "digs")
        
        # Incoming players from incoming_players.py
        incoming_for_team = [p for p in incoming_players if normalize_school_key(p["school"]) == team_key]
        
        # Categorize incoming by position
        inc_setters = []
        inc_pins = []
        inc_middles = []
        inc_defs = []
        
        for p in incoming_for_team:
            codes = extract_position_codes(p["position"])
            if ("S" in codes) and ("DS" not in codes):
                inc_setters.append(p)
            if ("OH" in codes) or ("RS" in codes):
                inc_pins.append(p)
            if "MB" in codes:
                inc_middles.append(p)
            if "DS" in codes:
                inc_defs.append(p)
        
        def format_incoming(players):
            return ", ".join([f"{p['name']} ({p['position']})" for p in players])
        
        inc_setter_names = format_incoming(inc_setters)
        inc_pin_names = format_incoming(inc_pins)
        inc_middle_names = format_incoming(inc_middles)
        inc_def_names = format_incoming(inc_defs)
        
        # Projected counts
        proj_setter_count = len(ret_setters) + len(inc_setters)
        proj_pin_count = len(ret_pins) + len(inc_pins)
        proj_middle_count = len(ret_middles) + len(inc_middles)
        proj_def_count = len(ret_defs) + len(inc_defs)
        
        # Transfers
        outgoing_xfers = outgoing_by_team.get(team_key, [])
        incoming_xfers = incoming_by_team.get(team_key, [])
        
        def format_transfers(xfers):
            return ", ".join([f"{x['name']}" for x in xfers])
        
        outgoing_transfers_str = format_transfers(outgoing_xfers)
        incoming_transfers_str = format_transfers(incoming_xfers)
        
        # Average heights
        def avg_height(players):
            heights = [height_to_inches(p["height"]) for p in players]
            heights = [h for h in heights if not pd.isna(h)]
            if heights:
                return inches_to_height(sum(heights) / len(heights))
            return ""
        
        avg_setter_height = avg_height(ret_setters)
        avg_pin_height = avg_height(ret_pins)
        avg_middle_height = avg_height(ret_middles)
        avg_def_height = avg_height(ret_defs)
        
        # Offense type (based on assists >= 350)
        setters_with_assists = [p for p in players_data if p["is_setter"] and p["assists"] >= 350]
        if len(setters_with_assists) >= 2:
            offense_type = "6-2"
        elif len(setters_with_assists) == 1:
            offense_type = "5-1"
        else:
            offense_type = "Unknown"
        
        # Get coaches (scrape if URLs available)
        coach_cols = {}
        if roster_url:
            try:
                roster_html = fetch_html(roster_url)
                coaches_html = roster_html
                
                alt_coaches_url = find_coaches_page_url(roster_html, roster_url)
                if alt_coaches_url:
                    try:
                        coaches_html = fetch_html(alt_coaches_url)
                    except:
                        pass
                
                coaches = parse_coaches_from_html(coaches_html)
                coach_cols = pack_coaches_for_row(coaches)
            except Exception as e:
                logger.warning("Could not fetch coaches for %s: %s", team_name, e)
        
        # Build result row
        result = {
            "team": team_name,
            "conference": conference,
            "rank": rank,
            "record": record,
            "roster_url": roster_url,
            "stats_url": stats_url,
            
            "returning_setter_count": len(ret_setters),
            "returning_setter_names": ret_setter_names,
            "incoming_setter_count": len(inc_setters),
            "incoming_setter_names": inc_setter_names,
            "projected_setter_count": proj_setter_count,
            "avg_setter_height": avg_setter_height,
            
            "returning_pin_count": len(ret_pins),
            "returning_pin_names": ret_pin_names,
            "incoming_pin_count": len(inc_pins),
            "incoming_pin_names": inc_pin_names,
            "projected_pin_count": proj_pin_count,
            "avg_pin_height": avg_pin_height,
            
            "returning_middle_count": len(ret_middles),
            "returning_middle_names": ret_middle_names,
            "incoming_middle_count": len(inc_middles),
            "incoming_middle_names": inc_middle_names,
            "projected_middle_count": proj_middle_count,
            "avg_middle_height": avg_middle_height,
            
            "returning_def_count": len(ret_defs),
            "returning_def_names": ret_def_names,
            "incoming_def_count": len(inc_defs),
            "incoming_def_names": inc_def_names,
            "projected_def_count": proj_def_count,
            "avg_def_height": avg_def_height,
            
            "outgoing_transfers": outgoing_transfers_str,
            "incoming_transfers": incoming_transfers_str,
            
            "offense_type": offense_type,
        }
        
        result.update(coach_cols)
        results.append(result)
    
    # Write output
    logger.info("Writing team pivot to: %s", output_csv)
    
    if results:
        fieldnames = list(results[0].keys())
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        logger.info("Wrote %d team rows", len(results))
    else:
        logger.warning("No results to write")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate team-level pivot analysis from scraper output")
    parser.add_argument(
        "--input",
        default=INPUT_CSV,
        help=f"Input CSV file (default: {INPUT_CSV})"
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_CSV,
        help=f"Output CSV file (default: {OUTPUT_CSV})"
    )
    args = parser.parse_args()
    
    setup_logging()
    main(input_csv=args.input, output_csv=args.output)
