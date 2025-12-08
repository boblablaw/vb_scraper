# create_team_pivot_csv.py
# Reads merged roster/stats output and calculates team-level aggregations
# including positional analysis, transfers, incoming players, coaches, and offense type.
# Coaches are pulled directly from settings/teams.json (populated via fetch_coaches.py).

import argparse
import csv
import re
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd

from scripts.helpers.teams_loader import load_teams
from settings import OUTGOING_TRANSFERS, RPI_TEAM_NAME_ALIASES
from scripts.helpers.utils import (
    normalize_school_key,
    normalize_player_name,
    normalize_class,
    class_next_year,
    is_graduating,
    extract_position_codes,
    normalize_text,
)
from scripts.helpers.coaches_cache import pack_coaches_for_row
from scripts.helpers.logging_utils import setup_logging, get_logger
from scripts.helpers.rpi_lookup import build_rpi_lookup

logger = get_logger(__name__)

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

INPUT_CSV = os.path.join(EXPORT_DIR, "ncaa_wvb_merged_2025.csv")
OUTPUT_CSV = os.path.join(EXPORT_DIR, "team_pivot.csv")

RPI_ALIAS_NORMALIZED_MAP = {
    normalize_text(alias): canonical
    for alias, canonical in RPI_TEAM_NAME_ALIASES.items()
    if alias
}


def resolve_canonical_team_name(name: str) -> str:
    """Return the canonical team name using the alias map when available."""
    if not name:
        return ""
    normalized = normalize_text(name)
    if not normalized:
        return ""
    return RPI_ALIAS_NORMALIZED_MAP.get(normalized, name)


def parse_incoming_players() -> List[Dict[str, str]]:
    """
    Parse incoming players from RAW_INCOMING_TEXT.
    Returns list of dicts with: name, school, position
    """
    from settings import RAW_INCOMING_TEXT

    players = []
    current_conf = ""

    for line in RAW_INCOMING_TEXT.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.endswith(":"):
            current_conf = line[:-1].strip()
            continue
        if " - " not in line:
            continue
        parts = line.split(" - ")
        if len(parts) < 3:
            continue
        name, school, position_raw = parts[0].strip(), parts[1].strip(), parts[2].strip()

        # Capture transfer flag from the parenthetical, then strip it for position codes.
        is_transfer = "transfer" in position_raw.lower()
        position = position_raw.split("(")[0].strip() if "(" in position_raw else position_raw
        players.append({
            "name": normalize_player_name(name),
            "school": school,
            "position": position,
            "conference": current_conf,
            "is_transfer": is_transfer,
        })

    return players


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


def _get_cached_rpi_lookup() -> Dict[str, Dict[str, str]]:
    """
    Try to load RPI lookup from cache; if missing, fetch and cache it.
    """
    cache_path = Path(EXPORT_DIR) / "rpi_lookup_cache.json"
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    logger.info("Loaded cached RPI lookup from %s", cache_path)
                    return data
        except Exception:
            pass

    lookup = build_rpi_lookup()
    if lookup:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(lookup, f, ensure_ascii=False, indent=2)
            logger.info("Cached RPI lookup to %s", cache_path)
        except Exception:
            logger.warning("Could not write RPI cache to %s", cache_path)
    return lookup


def main(input_csv=None, output_csv=None, teams_json_path=None):
    """
    Generate team pivot CSV from scraper output.
    
    Args:
        input_csv: Input CSV file with per-player data
        output_csv: Output CSV file for team-level data
        teams_json_path: Optional custom path to teams.json (default uses loader default)
    """
    input_csv = input_csv or INPUT_CSV
    output_csv = output_csv or OUTPUT_CSV
    teams_data = load_teams(teams_json_path)
    team_meta_lookup = {
        normalize_school_key(t.get("team", "")): t for t in teams_data
    }
    team_coach_lookup = {
        k: v.get("coaches", []) or [] for k, v in team_meta_lookup.items()
    }
    
    logger.info("Reading simplified scraper output: %s", input_csv)
    
    # Read the simplified CSV
    df = pd.read_csv(input_csv)
    
    # Normalize column names for merged NCAA file
    df = df.rename(
        columns={
            "School": "team",       # primary team field
            "Team": "stats_team",   # display name from stats
            "Conference": "conference",
            "Player": "name",
            "Yr": "class",
            "Pos": "position",
            "Ht": "height",
            "Hit Pct": "hitting_pct",
            "Assists": "assists",
            "Digs": "digs",
            "Kills": "kills",
            "PTS": "points",
        }
    )
    # Default values if missing
    if "team" not in df.columns and "stats_team" in df.columns:
        df["team"] = df["stats_team"]
    
    # Build lookup of existing players (for transfers class/pos lookup)
    player_lookup = {}
    for _, row in df.iterrows():
        key = normalize_player_name(str(row.get("name", "")))
        if not key:
            continue
        pos_codes = extract_position_codes(str(row.get("position", "")))
        class_norm = normalize_class(str(row.get("class", "")))
        player_lookup[key] = {
            "position_raw": str(row.get("position", "")),
            "pos_codes": pos_codes,
            "class_norm": class_norm,
            "class_next": class_next_year(class_norm),
        }

    # Parse incoming players
    logger.info("Parsing incoming players...")
    incoming_players = parse_incoming_players()
    
    # Build RPI lookup (with cache fallback)
    logger.info("Fetching RPI data...")
    rpi_lookup = _get_cached_rpi_lookup()
    if rpi_lookup:
        logger.info(f"Loaded RPI data for {len(rpi_lookup)} teams")
    else:
        logger.warning("No RPI data available")
    
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
        team_info = team_meta_lookup.get(team_key, {})
        
        # Get team metadata
        conference = team_df["conference"].iloc[0] if "conference" in team_df.columns else ""
        
        # Get RPI rank and record from RPI lookup using canonical team names
        stats_team_name = team_df["stats_team"].iloc[0] if "stats_team" in team_df.columns else team_name
        stats_team_canonical = resolve_canonical_team_name(stats_team_name)
        if not stats_team_canonical:
            stats_team_canonical = resolve_canonical_team_name(team_name)
        if not stats_team_canonical:
            stats_team_canonical = team_name
        stats_team_key = normalize_school_key(stats_team_canonical)
        rpi_data = rpi_lookup.get(stats_team_key, {}) or rpi_lookup.get(team_key, {})
        rank = rpi_data.get("rpi_rank", "")
        record = rpi_data.get("rpi_record", "")
        roster_url = team_info.get("url", "")
        stats_url = team_info.get("stats_url", "")
        
        # Calculate positional flags for each player (input already normalized)
        players_data = []
        for _, row in team_df.iterrows():
            position_raw = str(row.get("position", ""))
            pos_codes = extract_position_codes(position_raw)

            has_s = "S" in pos_codes
            has_pin = ("OH" in pos_codes) or ("RS" in pos_codes)
            has_middle = "MB" in pos_codes
            has_def = "DS" in pos_codes

            # Treat setters only when they are pure setters or RS/S.
            # Exclude hybrid OH/S or MB/S from the setter count.
            is_setter = False
            if has_s:
                if has_middle or ("OH" in pos_codes):
                    is_setter = False
                elif "RS" in pos_codes:
                    is_setter = True
                elif not has_pin and not has_def:
                    is_setter = True

            is_pin = has_pin
            is_middle = has_middle
            is_def = has_def
            
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

            assists_val = to_int_safe(row.get("assists", 0))
            
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
                "assists": assists_val,
                "kills": to_int_safe(row.get("kills", 0)),
                "digs": to_int_safe(row.get("digs", 0)),
            })
        
        # Calculate returning players (not graduating, not outgoing transfer)
        returning_players = [p for p in players_data if not p["is_graduating"] and not p["is_outgoing_transfer"]]
        
        # Returning by position
        ret_setters = [p for p in returning_players if p["is_setter"]]
        # Count any returning player with meaningful assists as a setter, even if hybrid
        ret_setters_assist_bonus = [
            p for p in returning_players if p["assists"] >= 150 and p not in ret_setters
        ]
        ret_setters_extended = ret_setters + ret_setters_assist_bonus
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
        
        ret_setter_names = format_returning(ret_setters_extended, "assists")
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
            parts = []
            for p in players:
                name = p["name"]
                pos_label = p["position"]
                is_transfer = p.get("is_transfer", False)

                class_disp = ""
                lookup = player_lookup.get(normalize_player_name(name), {})
                class_next = lookup.get("class_next") or lookup.get("class_norm") or ""
                if class_next:
                    class_disp = class_next
                    if not class_disp.endswith("."):
                        class_disp = f"{class_disp}."

                # Prefer clean position label from codes if available
                codes = lookup.get("pos_codes") or extract_position_codes(pos_label)
                if "S" in codes and len(codes) == 1:
                    pos_label_fmt = "Setter"
                elif "MB" in codes and len(codes) == 1:
                    pos_label_fmt = "Middle"
                elif "OH" in codes or "RS" in codes:
                    pos_label_fmt = "Pin"
                elif "DS" in codes:
                    pos_label_fmt = "Defender"
                else:
                    pos_label_fmt = pos_label

                if is_transfer:
                    suffix = " - Transfer"
                    parts.append(
                        f"{name} ({class_disp} {pos_label_fmt}{suffix})"
                        .replace("  ", " ")
                        .replace("( ", "(")
                        .replace(" )", ")")
                    )
                else:
                    parts.append(f"{name} ({pos_label})")
            return ", ".join(parts)
        
        inc_setter_names = format_incoming(inc_setters)
        inc_pin_names = format_incoming(inc_pins)
        inc_middle_names = format_incoming(inc_middles)
        inc_def_names = format_incoming(inc_defs)
        
        # Projected counts
        proj_setter_count = len(ret_setters_extended) + len(inc_setters)
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
        
        avg_setter_height = avg_height(ret_setters_extended)
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
        
        # Get coaches from teams.json lookup
        coach_cols = {}
        coaches = team_coach_lookup.get(team_key, [])
        if coaches:
            coach_cols = pack_coaches_for_row(coaches)
        else:
            coach_cols = pack_coaches_for_row([])
        
        # Build result row
        result = {
            "team": team_name,
            "conference": conference,
            "roster_url": roster_url,
            "stats_url": stats_url,
            "rank": rank,
            "record": record,
            "offense_type": offense_type,
            
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
    parser.add_argument(
        "--teams-json",
        default=None,
        help="Optional path to teams.json (default: settings/teams.json)"
    )
    args = parser.parse_args()
    
    setup_logging()
    main(
        input_csv=args.input,
        output_csv=args.output,
        teams_json_path=args.teams_json,
    )
