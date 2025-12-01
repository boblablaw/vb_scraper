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
MAIN_EXPORT = "exports/rosters_and_stats.csv"

# Map file name prefixes to official team names
# Note: Auto-matching using normalize_school_key is attempted first
# Only add explicit mappings here if auto-matching fails
TEAM_NAME_MAP = {
    # Add explicit overrides here if needed
}


def extract_team_from_filename(filename: str) -> str:
    """
    Extract team identifier from filename.
    Example: coastal_carolina_stats.csv -> coastal_carolina
            northern colorado_stats(1).csv -> northern colorado
    """
    # Remove .csv extension
    base = filename.replace(".csv", "")
    # Remove (1), (2), etc. suffix (browser download duplicates)
    base = re.sub(r"\(\d+\)$", "", base).strip()
    # Remove _stats or _stats1 suffix
    base = re.sub(r"_stats\d*$", "", base)
    return base


def parse_manual_stats_file(filepath: str) -> pd.DataFrame:
    """
    Parse a manually downloaded stats CSV file.
    Returns DataFrame with player names and stats.
    """
    try:
        # Read CSV with header=None to inspect structure
        df_raw = pd.read_csv(filepath, header=None)
        
        # Row 0 is category headers, row 1 is stat names (our actual headers)
        # Row 2+ are data rows
        if len(df_raw) < 2:
            return pd.DataFrame()
        
        # Use row 1 as column names, but handle duplicates and empties
        stat_names_raw = df_raw.iloc[1].tolist()
        
        # Detect if there's a missing column header (e.g., PTS total missing at index 5)
        # This happens in SIDEARM stats exports where a column exists but has no name
        # Look for pattern: empty column followed by stat names that don't align with data
        has_offset = False
        empty_indices = []
        for i, name in enumerate(stat_names_raw):
            name_str = str(name).strip() if pd.notna(name) else ""
            if not name_str and i > 1:  # Skip jersey and player columns
                empty_indices.append(i)
        
        # If we find an empty column in the middle (after player name), there's likely an offset
        # Common pattern: col 5 is empty (should be PTS) causing all subsequent names to shift left
        if empty_indices and 4 <= empty_indices[0] <= 6:
            has_offset = True
            print(f"  Detected missing column header at index {empty_indices[0]} - will use positional mapping")
        
        # Make column names unique by appending index to duplicates/empties
        stat_names = []
        seen = {}
        for i, name in enumerate(stat_names_raw):
            # Convert to string and strip whitespace
            name_str = str(name).strip() if pd.notna(name) else ""
            
            # If empty or duplicate, make it unique
            if not name_str or name_str in seen:
                # Use column index as name for empty/duplicate columns
                unique_name = f"col_{i}"
                stat_names.append(unique_name)
                seen[unique_name] = 1
            else:
                stat_names.append(name_str)
                seen[name_str] = 1
        
        # Read data starting from row 2 (skip rows 0 and 1)
        df = pd.read_csv(filepath, skiprows=2, names=stat_names)
        
        # If we detected an offset, rename columns based on position
        if has_offset:
            # Standard SIDEARM offensive stats column positions:
            # 0:#, 1:Player, 2:SP, 3:MP, 4:MS, 5:PTS(total), 6:PTS/S, 7:K, 8:K/S, 9:E, 10:TA, 11:PCT, 12:A, 13:A/S, 14:SA, 15:SA/S, 16:SE
            # Standard SIDEARM defensive stats column positions:
            # 0:#, 1:Player, 2:SP, 3:DIG, 4:DIG/S, 5:empty, 6:RE, 7:TA, 8:Rec%, 9:RE/S, 10:BS, 11:BA, 12:BLK, 13:BLK/S, 14:BE, 15:BHE
            
            # Try to detect if this is offensive or defensive stats
            is_offensive = 'K' in stat_names or 'PTS' in stat_names or 'A' in stat_names
            
            if is_offensive and len(stat_names) >= 17:
                # Map by position for offensive stats
                positional_names = [
                    stat_names[0],  # 0: # (jersey)
                    stat_names[1],  # 1: Player
                    'SP',   # 2
                    'MP',   # 3
                    'MS',   # 4
                    'PTS_total',  # 5 (unnamed in header)
                    'PTS/S',  # 6
                    'K',    # 7
                    'K/S',  # 8
                    'E',    # 9
                    'TA',   # 10
                    'PCT',  # 11
                    'A',    # 12
                    'A/S',  # 13
                    'SA',   # 14
                    'SA/S', # 15
                    'SE',   # 16
                ] + stat_names[17:]  # Keep any additional columns
                df.columns = positional_names[:len(df.columns)]
            elif not is_offensive and len(stat_names) >= 15:
                # Map by position for defensive stats
                # Correct mapping (based on data positions):
                # 0:#, 1:Player, 2:SP, 3:DIG, 4:DIG/S, 5:RE, 6:TA_RECV, 7:Rec%, 8:RE/S, 9:BS, 10:BA, 11:BLK, 12:BLK/S, 13:BE, 14:BHE, 15:Bio
                positional_names = [
                    stat_names[0],  # 0: # (jersey)
                    stat_names[1],  # 1: Player
                    'SP',       # 2
                    'DIG',      # 3
                    'DIG/S',    # 4
                    'RE',       # 5 (reception errors - unnamed in header)
                    'TA_RECV',  # 6 (total reception attempts)
                    'Rec%',     # 7 (reception percentage)
                    'RE/S',     # 8 (reception errors per set)
                    'BS',       # 9
                    'BA',       # 10
                    'BLK',      # 11 (total blocks)
                    'BLK/S',    # 12
                    'BE',       # 13 (blocking errors)
                    'BHE',      # 14 (ball handling errors)
                    'Bio',      # 15 (bio link / unused)
                ] + stat_names[16:]  # Keep any additional columns
                df.columns = positional_names[:len(df.columns)]
        
        # Filter out total/opponent rows
        if df.shape[1] > 1:
            # Second column usually has player names (should be 'Player' or col_1)
            player_col = None
            for col in df.columns[0:3]:  # Check first 3 columns
                if col.lower() == 'player' or 'player' in str(col).lower():
                    player_col = col
                    break
            
            if not player_col:
                player_col = df.columns[1]  # Fallback to second column
            
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
        'ta_recv': 'total_reception_attempts',  # TA in defensive stats means reception attempts
        'pct': 'hitting_pct',
        'rec%': 'reception_pct',
        'a': 'assists',
        'a/s': 'assists_per_set',
        'sa': 'aces',
        'sa/s': 'aces_per_set',
        'se': 'service_errors',
        'dig': 'digs',
        'dig/s': 'digs_per_set',
        're': 'reception_errors',
        're/s': 'reception_errors_per_set',
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
            # Map internal stat names to CSV abbreviated headers
            stat_col_map = {
                'matches_started': 'MS',
                'matches_played': 'MP',
                'sets_played': 'SP',
                'points': 'PTS',
                'points_per_set': 'PTS/S',
                'kills': 'K',
                'kills_per_set': 'K/S',
                'attack_errors': 'AE',
                'total_attacks': 'TA',
                'hitting_pct': 'HIT%',
                'assists': 'A',
                'assists_per_set': 'A/S',
                'aces': 'SA',
                'aces_per_set': 'SA/S',
                'service_errors': 'SE',
                'digs': 'D',
                'digs_per_set': 'D/S',
                'reception_errors': 'RE',
                'total_reception_attempts': 'TRE',
                'reception_pct': 'Rec%',
                'block_solos': 'BS',
                'block_assists': 'BA',
                'total_blocks': 'TB',
                'blocks_per_set': 'B/S',
                'ball_handling_errors': 'BHE',
            }
            
            for stat_col, stat_val in matched_stats.items():
                # Map to abbreviated column name
                csv_col = stat_col_map.get(stat_col, stat_col)
                if csv_col in main_df.columns:
                    main_df.at[idx, csv_col] = stat_val
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
        print(f"  Export players without stats: {', '.join(str(p) for p in unmatched_export[:5])}")
    if unmatched_stats:
        print(f"  Stats players not in export: {', '.join(str(p) for p in unmatched_stats[:5])}")
    
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
    
    # Load team list for intelligent matching
    from settings.teams import TEAMS
    all_team_names = [t['team'] for t in TEAMS]
    
    # Group files by team
    team_files = {}
    for filepath in stats_files:
        team_id = extract_team_from_filename(filepath.name)
        
        # First check explicit mapping
        if team_id in TEAM_NAME_MAP:
            team_name = TEAM_NAME_MAP[team_id]
        else:
            # Try intelligent matching using normalize_school_key
            team_id_normalized = normalize_school_key(team_id)
            
            # Find best match in team list
            best_match = None
            for candidate in all_team_names:
                if normalize_school_key(candidate) == team_id_normalized:
                    best_match = candidate
                    break
            
            if best_match:
                team_name = best_match
                print(f"Auto-matched: '{team_id}' -> '{best_match}'")
            else:
                # No match found, use original (will likely fail to match players)
                team_name = team_id
                print(f"Warning: No match found for '{team_id}' - add to TEAM_NAME_MAP if needed")
        
        if team_name not in team_files:
            team_files[team_name] = []
        team_files[team_name].append(str(filepath))
    
    # Load main export
    if not os.path.exists(MAIN_EXPORT):
        print(f"Main export not found: {MAIN_EXPORT}")
        return
    
    print(f"Loading main export: {MAIN_EXPORT}")
    main_df = pd.read_csv(MAIN_EXPORT)
    print(f"  {len(main_df)} rows, {main_df['Team'].nunique()} teams")
    
    # Process each team
    for team_name, files in team_files.items():
        main_df = merge_stats_for_team(team_name, files, main_df)
    
    # Write updated export (CSV only)
    print()
    print(f"Writing updated export to {MAIN_EXPORT}")
    main_df.to_csv(MAIN_EXPORT, index=False)
    print()
    print("Done!")


if __name__ == '__main__':
    main()
