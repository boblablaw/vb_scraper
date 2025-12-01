#!/usr/bin/env python3
"""
Merge manually downloaded stats files from stats/ directory into the main export.

Usage:
    python merge_manual_stats.py
    
Expected stats file naming: <team_identifier>_stats.csv or <team_identifier>_stats1.csv
Example: coastal_carolina_stats.csv, coastal_carolina_stats1.csv

The script will:
1. Read all CSV files from stats/ directory
2. Extract team name from filename
3. Parse player stats from the CSV files
4. Match players by name to the main export
5. Update player stats in the export
"""

import os
import re
import pandas as pd
from pathlib import Path
from scraper.utils import normalize_player_name, normalize_school_key

STATS_DIR = "stats"
MAIN_EXPORT = "exports/d1_rosters_2026_with_stats_and_incoming.tsv"

# Map file name prefixes to official team names
TEAM_NAME_MAP = {
    "coastal_carolina": "Coastal Carolina University",
    # Add more mappings as needed
}


def extract_team_from_filename(filename: str) -> str:
    """
    Extract team identifier from filename.
    Example: coastal_carolina_stats.csv -> coastal_carolina
    """
    # Remove .csv extension
    base = filename.replace(".csv", "")
    # Remove _stats or _stats1 suffix
    base = re.sub(r"_stats\d*$", "", base)
    return base


def parse_manual_stats_file(filepath: str) -> pd.DataFrame:
    """
    Parse a manually downloaded stats CSV file.
    Returns DataFrame with player names and stats.
    """
    try:
        # Read CSV - first row has category headers, second row has stat names
        df = pd.read_csv(filepath, skiprows=1)  # Skip category row, use stat names
        
        # Filter out total/opponent rows
        if df.shape[1] > 1:
            # Second column usually has player names
            player_col = df.columns[1]
            df = df[~df[player_col].astype(str).str.contains('Total|Opponents', case=False, na=False)]
            # Rename player column to 'Player' for easier access
            df = df.rename(columns={player_col: 'Player'})
        
        return df
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return pd.DataFrame()


def clean_player_name(raw_name: str) -> str:
    """
    Clean player name from stats file.
    Example: "Earnhardt, Bailee                                             1Earnhardt, Bailee"
    -> "Bailee Earnhardt"
    """
    if not isinstance(raw_name, str):
        return ""
    
    # Remove extra whitespace and duplicates
    # Pattern: "Last, First [spaces] NumberLast, First" or similar
    name = raw_name.strip()
    
    # Find first occurrence of comma (Last, First)
    if "," in name:
        # Take everything up to potential duplicate or View Bio
        name = re.split(r'\s{2,}|\d+[A-Z]', name)[0]
        # Convert "Last, First" to "First Last"
        parts = name.split(",")
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"
    
    return normalize_player_name(name)


def normalize_stat_column(col: str) -> str:
    """
    Normalize stat column names to match main export format.
    """
    col = col.strip().lower()
    
    # Map to internal stat names
    mapping = {
        'sp': 'sets_played',
        'mp': 'matches_played',
        'ms': 'matches_started',
        'pts': 'points',
        'pts/s': 'points_per_set',
        'k': 'kills',
        'k/s': 'kills_per_set',
        'e': 'attack_errors',
        'ta': 'total_attacks',
        'pct': 'hitting_pct',
        'a': 'assists',
        'a/s': 'assists_per_set',
        'sa': 'aces',
        'sa/s': 'aces_per_set',
        'se': 'service_errors',
        'dig': 'digs',
        'dig/s': 'digs_per_set',
        're': 'reception_errors',
        'bs': 'block_solos',
        'ba': 'block_assists',
        'blk': 'total_blocks',
        'blk/s': 'blocks_per_set',
        'be': 'ball_handling_errors',
        'bhe': 'ball_handling_errors',
    }
    
    return mapping.get(col, col)


def merge_stats_for_team(team_name: str, stats_files: list, main_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge stats from multiple files for a team into the main dataframe.
    """
    print(f"\nProcessing {team_name}...")
    print(f"  Stats files: {[os.path.basename(f) for f in stats_files]}")
    
    # Combine all stats files for this team
    all_stats = {}
    
    for filepath in stats_files:
        stats_df = parse_manual_stats_file(filepath)
        if stats_df.empty:
            continue
        
        # Normalize column names
        stats_df.columns = [normalize_stat_column(c) for c in stats_df.columns]
        
        # Process each player
        for _, row in stats_df.iterrows():
            player_raw = row.get('player', '')
            if not player_raw:
                continue
            
            player_name = clean_player_name(player_raw)
            if not player_name:
                continue
            
            # Store stats for this player (merge from multiple files)
            if player_name not in all_stats:
                all_stats[player_name] = {}
            
            # Add all numeric stats
            for col, val in row.items():
                if col != 'player' and col != '#' and pd.notna(val):
                    # Convert to numeric if possible
                    try:
                        all_stats[player_name][col] = float(val)
                    except (ValueError, TypeError):
                        pass
    
    print(f"  Found {len(all_stats)} players in stats files")
    
    # Match players in main export and update stats
    team_mask = main_df['Team'] == team_name
    team_players = main_df[team_mask]
    
    matched = 0
    unmatched_stats = []
    unmatched_export = []
    
    for idx, player_row in team_players.iterrows():
        export_name = normalize_player_name(player_row['Name'])
        
        # Try to find match in stats
        matched_stats = None
        for stats_name, stats in all_stats.items():
            if stats_name == export_name:
                matched_stats = stats
                break
        
        if matched_stats:
            # Update stats in main dataframe
            for stat_col, stat_val in matched_stats.items():
                # Map to friendly column name
                friendly_col = stat_col.replace('_', ' ').title()
                if friendly_col in main_df.columns:
                    main_df.at[idx, friendly_col] = stat_val
            matched += 1
        else:
            unmatched_export.append(player_row['Name'])
    
    # Find stats players not matched to export
    for stats_name in all_stats.keys():
        found = False
        for idx, player_row in team_players.iterrows():
            export_name = normalize_player_name(player_row['Name'])
            if stats_name == export_name:
                found = True
                break
        if not found:
            unmatched_stats.append(stats_name)
    
    print(f"  Matched {matched} players")
    if unmatched_export:
        print(f"  Export players without stats: {', '.join(unmatched_export[:5])}")
    if unmatched_stats:
        print(f"  Stats players not in export: {', '.join(unmatched_stats[:5])}")
    
    return main_df


def main():
    print("Manual Stats Merge Tool")
    print("=" * 80)
    print()
    
    # Check if stats directory exists
    if not os.path.exists(STATS_DIR):
        print(f"Stats directory not found: {STATS_DIR}")
        return
    
    # Find all CSV files in stats directory
    stats_files = list(Path(STATS_DIR).glob("*.csv"))
    if not stats_files:
        print(f"No CSV files found in {STATS_DIR}")
        return
    
    print(f"Found {len(stats_files)} stats files:")
    for f in stats_files:
        print(f"  - {f.name}")
    print()
    
    # Group files by team
    team_files = {}
    for filepath in stats_files:
        team_id = extract_team_from_filename(filepath.name)
        team_name = TEAM_NAME_MAP.get(team_id, team_id)
        
        if team_name not in team_files:
            team_files[team_name] = []
        team_files[team_name].append(str(filepath))
    
    # Load main export
    if not os.path.exists(MAIN_EXPORT):
        print(f"Main export not found: {MAIN_EXPORT}")
        return
    
    print(f"Loading main export: {MAIN_EXPORT}")
    main_df = pd.read_csv(MAIN_EXPORT, sep='\t')
    print(f"  {len(main_df)} rows, {main_df['Team'].nunique()} teams")
    
    # Process each team
    for team_name, files in team_files.items():
        main_df = merge_stats_for_team(team_name, files, main_df)
    
    # Write updated export
    print()
    print(f"Writing updated export to {MAIN_EXPORT}")
    main_df.to_csv(MAIN_EXPORT, sep='\t', index=False)
    
    # Also write CSV version
    csv_file = MAIN_EXPORT.replace('.tsv', '.csv')
    main_df.to_csv(csv_file, index=False)
    print(f"Also wrote: {csv_file}")
    print()
    print("Done!")


if __name__ == '__main__':
    main()
