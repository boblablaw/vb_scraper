#!/usr/bin/env python3
"""Export transfers from transfers.json to CSV file."""

import csv
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from settings import OUTGOING_TRANSFERS
from scripts.helpers.utils import (
    normalize_class,
    class_next_year,
    extract_position_codes,
    normalize_school_key,
    normalize_player_name,
)

# Optional lookup from scraped roster/stats to enrich position/class
ROSTER_STATS_PATH = ROOT / "exports" / "rosters_and_stats.csv"


def _build_roster_lookup():
    if not ROSTER_STATS_PATH.exists():
        return {}
    import pandas as pd

    df = pd.read_csv(ROSTER_STATS_PATH)
    lookup = {}
    for _, row in df.iterrows():
        team = normalize_school_key(str(row.get("Team", "")))
        name = normalize_player_name(str(row.get("Name", "")))
        if not team or not name:
            continue
        lookup[(team, name)] = {
            "position": row.get("Position", ""),
            "class": row.get("Class", ""),
        }
    return lookup


def export_to_csv():
    """Export OUTGOING_TRANSFERS to CSV file."""
    # Create exports directory if it doesn't exist
    exports_dir = Path(__file__).parent / "exports"
    exports_dir.mkdir(exist_ok=True)

    roster_lookup = _build_roster_lookup()
    
    # Define output file path
    output_file = exports_dir / "outgoing_transfers.csv"
    
    # Write to CSV; include year field if present
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "name",
            "old_team",
            "new_team",
            "year",
            "position",
            "position_norm",
            "class",
            "class_next",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in OUTGOING_TRANSFERS:
            pos_raw = row.get("position", "") if isinstance(row, dict) else ""
            codes = extract_position_codes(str(pos_raw))
            # If no position in transfers.json, try roster lookup
            name_norm = normalize_player_name(row.get("name", "")) if isinstance(row, dict) else ""
            team_norm = normalize_school_key(row.get("old_team", "")) if isinstance(row, dict) else ""
            if not codes and (team_norm, name_norm) in roster_lookup:
                pos_raw = roster_lookup[(team_norm, name_norm)].get("position", pos_raw)
                codes = extract_position_codes(str(pos_raw))

            if "S" in codes and len(codes) == 1:
                pos_norm = "Setter"
            elif "MB" in codes and len(codes) == 1:
                pos_norm = "Middle"
            elif "OH" in codes or "RS" in codes:
                pos_norm = "Pin"
            elif "DS" in codes or "L" in codes:
                pos_norm = "Defender"
            else:
                pos_norm = pos_raw

            cls_raw = row.get("class") if isinstance(row, dict) else None
            if not cls_raw and (team_norm, name_norm) in roster_lookup:
                cls_raw = roster_lookup[(team_norm, name_norm)].get("class")
            cls_norm = normalize_class(str(cls_raw)) if cls_raw else ""
            cls_next = class_next_year(cls_norm) if cls_norm else ""

            writer.writerow({
                "name": row.get("name"),
                "old_team": row.get("old_team"),
                "new_team": row.get("new_team"),
                "year": row.get("year"),
                "position": pos_raw,
                "position_norm": pos_norm,
                "class": cls_norm,
                "class_next": cls_next,
            })
    
    print(f"✓ Exported {len(OUTGOING_TRANSFERS)} transfers to {output_file}")


if __name__ == "__main__":
    export_to_csv()
