#!/usr/bin/env python3
"""
Merge manually-entered roster data with scraped data.

This script reads manual_rosters.csv and merges it with the scraped roster data.
Use this for teams with JavaScript-rendered rosters that can't be scraped automatically.

Usage:
    python merge_manual_rosters.py
    
The script will:
1. Read manual_rosters.csv from settings/
2. Read the scraped data from exports/
3. Add manual roster entries for teams with:
   - RPI data lookup
   - Class year progression calculation
   - Transfer matching
   - Incoming player matching
4. Write updated exports with manual data included
"""

import pandas as pd
from pathlib import Path
from scraper.utils import (
    normalize_class, 
    normalize_height,
    normalize_school_key
)


def load_manual_rosters(manual_file: str = 'settings/manual_rosters.csv') -> pd.DataFrame:
    """Load manually-entered roster data."""
    try:
        df = pd.read_csv(manual_file)
        # Remove empty rows (template rows with no name)
        df = df[df['Name'].notna() & (df['Name'].str.strip() != '')]
        return df
    except FileNotFoundError:
        print(f'Warning: Manual roster file not found: {manual_file}')
        return pd.DataFrame(columns=['Team', 'Name', 'Position', 'Class', 'Height'])
    except Exception as e:
        print(f'Error loading manual rosters: {e}')
        return pd.DataFrame(columns=['Team', 'Name', 'Position', 'Class', 'Height'])


def merge_manual_with_scraped(scraped_file: str, manual_df: pd.DataFrame, output_file: str):
    """Merge manual roster data with scraped data."""
    
    # Load scraped data
    try:
        scraped_df = pd.read_csv(scraped_file)
    except Exception as e:
        print(f'Error loading scraped data from {scraped_file}: {e}')
        return
    
    print(f'Loaded scraped data: {len(scraped_df)} rows from {scraped_df["Team"].nunique()} teams')
    
    if len(manual_df) == 0:
        print('No manual roster data to merge')
        print(f'Using scraped data as-is: {output_file}')
        scraped_df.to_csv(output_file, sep='\t', index=False)
        return
    
    print(f'Loaded manual data: {len(manual_df)} players from {manual_df["Team"].nunique()} teams')
    print()
    
    # Get list of teams in manual data
    manual_teams = set(manual_df['Team'].unique())
    
    # Instead of removing teams, we'll merge by player name
    # Keep scraped data for teams with manual entries, but update/add players
    print(f'Processing {len(manual_teams)} teams with manual data (will merge with scraped data)')
    
    print()
    
    # Get conference info and URLs from settings
    from settings.teams import TEAMS
    team_info = {t['team']: t for t in TEAMS}
    
    # Process manual roster entries by team
    # Strategy: For each team with manual data, update/add players by matching names
    # Then recalculate projected counts for the entire team
    
    manual_updates = []  # Track updates/additions
    
    for team in sorted(manual_teams):
        team_players_manual = manual_df[manual_df['Team'] == team]
        team_data = team_info.get(team, {})
        norm_school = normalize_school_key(team)
        
        # Process each manual player entry
        for _, row in team_players_manual.iterrows():
            # Normalize data
            name = row['Name']
            position_raw = str(row['Position']) if pd.notna(row['Position']) else ''
            class_raw = str(row['Class']) if pd.notna(row['Class']) else ''
            height_raw = str(row['Height']) if pd.notna(row['Height']) else ''
            
            class_normalized = normalize_class(class_raw)
            height_normalized = normalize_height(height_raw)
            
            # Try to find existing player in scraped data
            existing_mask = (scraped_df['Team'] == team) & (scraped_df['Name'] == name)
            existing_player = scraped_df[existing_mask]
            
            if len(existing_player) > 0:
                # Update existing player - preserve stats, update roster fields
                idx = existing_player.index[0]
                scraped_df.at[idx, 'Position'] = position_raw
                scraped_df.at[idx, 'Class'] = class_normalized
                scraped_df.at[idx, 'Height'] = height_normalized
                manual_updates.append(('updated', team, name))
            else:
                # Add new player - create row with all scraped columns
                new_row = {
                    'Team': team,
                    'Conference': team_data.get('conference', ''),
                    'Name': name,
                    'Position': position_raw,
                    'Class': class_normalized,
                    'Height': height_normalized,
                }
                
                # Add empty columns for all other fields (stats, etc.)
                for col in scraped_df.columns:
                    if col not in new_row:
                        new_row[col] = None
                
                # Append to scraped_df
                scraped_df = pd.concat([scraped_df, pd.DataFrame([new_row])], ignore_index=True)
                manual_updates.append(('added', team, name))
    
    merged_df = scraped_df
    
    # Sort by team
    merged_df = merged_df.sort_values('Team')
    
    # Write merged data (CSV only)
    merged_df.to_csv(output_file, index=False)
    
    print()
    print(f'Merged data written to: {output_file}')
    print(f'  Total players: {len(merged_df)}')
    print(f'  Total teams: {merged_df["Team"].nunique()}')
    print()
    
    # Report on updates and additions
    updates_count = sum(1 for action, _, _ in manual_updates if action == 'updated')
    additions_count = sum(1 for action, _, _ in manual_updates if action == 'added')
    
    print(f'Manual roster changes:')
    print(f'  - Players updated: {updates_count}')
    print(f'  - Players added: {additions_count}')
    print(f'  - Teams processed: {len(manual_teams)}')
    print()
    print('Teams with manual data:')
    for team in sorted(manual_teams):
        team_updates = [(a, n) for a, t, n in manual_updates if t == team]
        updated = sum(1 for a, _ in team_updates if a == 'updated')
        added = sum(1 for a, _ in team_updates if a == 'added')
        print(f'  - {team}: {updated} updated, {added} added')


def main():
    """Main entry point."""
    import sys
    
    print('Manual Roster Merge Tool')
    print('=' * 80)
    print()
    
    # Parse command line arguments for custom paths
    scraped_file = 'exports/rosters_and_stats.csv'
    output_file = 'exports/rosters_and_stats.csv'
    
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    if '--input' in sys.argv:
        idx = sys.argv.index('--input')
        if idx + 1 < len(sys.argv):
            scraped_file = sys.argv[idx + 1]
    
    # Load manual rosters
    manual_df = load_manual_rosters('settings/manual_rosters.csv')
    
    if len(manual_df) == 0:
        print('No manual roster data found. Add player data to settings/manual_rosters.csv')
        print()
        print('Format: Team,Name,Position,Class,Height')
        print('Example: University of Alabama,Jane Doe,OH,Jr,6-2')
        return
    
    # Merge with main scraped data
    merge_manual_with_scraped(
        scraped_file=scraped_file,
        manual_df=manual_df,
        output_file=output_file
    )


if __name__ == '__main__':
    main()
