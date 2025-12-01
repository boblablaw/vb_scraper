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
    class_next_year, 
    is_graduating,
    normalize_height,
    extract_position_codes,
    normalize_player_name,
    normalize_school_key
)
from scraper.incoming_players import get_incoming_players
from settings.transfers_config import OUTGOING_TRANSFERS


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
    
    # Load supplementary data
    print('Loading incoming players data...')
    incoming_players = get_incoming_players()
    
    print('Loading transfers data...')
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
            
            position_normalized = position_raw
            class_normalized = normalize_class(class_raw)
            height_normalized = normalize_height(height_raw)
            class_next = class_next_year(class_normalized)
            
            # Extract position codes
            position_codes = extract_position_codes(position_raw)
            # Do NOT count S/DS as a setter
            is_setter = 1 if ('S' in position_codes and 'DS' not in position_codes) else 0
            is_pin = 1 if ('OH' in position_codes or 'RS' in position_codes) else 0
            is_middle = 1 if 'MB' in position_codes else 0
            is_ds = 1 if 'DS' in position_codes else 0
            
            # Check if graduating
            is_grad = 1 if is_graduating(class_normalized) else 0
            
            # Check for outgoing transfer
            norm_name = normalize_player_name(name)
            is_outgoing = 0
            for transfer in OUTGOING_TRANSFERS:
                if (normalize_player_name(transfer['name']) == norm_name and
                    normalize_school_key(transfer['old_team']) == norm_school):
                    is_outgoing = 1
                    break
            
            # Check for incoming transfer
            is_incoming = 0
            for inc in incoming_players:
                if (normalize_player_name(inc['name']) == norm_name and
                    normalize_school_key(inc['school']) == norm_school):
                    is_incoming = 1
                    break
            
            # Try to find existing player in scraped data
            existing_mask = (scraped_df['Team'] == team) & (scraped_df['Name'] == name)
            existing_player = scraped_df[existing_mask]
            
            if len(existing_player) > 0:
                # Update existing player - preserve stats, update roster fields
                idx = existing_player.index[0]
                scraped_df.at[idx, 'Position Raw'] = position_raw
                scraped_df.at[idx, 'Position'] = position_normalized
                scraped_df.at[idx, 'Class Raw'] = class_raw
                scraped_df.at[idx, 'Class'] = class_normalized
                scraped_df.at[idx, 'Class Next Year'] = class_next
                scraped_df.at[idx, 'Height Raw'] = height_raw
                scraped_df.at[idx, 'Height'] = height_normalized
                scraped_df.at[idx, 'Is Setter'] = is_setter
                scraped_df.at[idx, 'Is Pin Hitter'] = is_pin
                scraped_df.at[idx, 'Is Middle Blocker'] = is_middle
                scraped_df.at[idx, 'Is Def Specialist'] = is_ds
                scraped_df.at[idx, 'Is Graduating'] = is_grad
                scraped_df.at[idx, 'Is Outgoing Transfer'] = is_outgoing
                scraped_df.at[idx, 'Is Incoming Transfer'] = is_incoming
                manual_updates.append(('updated', team, name))
            else:
                # Add new player - create row with all scraped columns
                new_row = {
                    'Team': team,
                    'Conference': team_data.get('conference', ''),
                    'Name': name,
                    'Position Raw': position_raw,
                    'Position': position_normalized,
                    'Class Raw': class_raw,
                    'Class': class_normalized,
                    'Class Next Year': class_next,
                    'Height Raw': height_raw,
                    'Height': height_normalized,
                    'Is Setter': is_setter,
                    'Is Pin Hitter': is_pin,
                    'Is Middle Blocker': is_middle,
                    'Is Def Specialist': is_ds,
                    'Is Graduating': is_grad,
                    'Is Outgoing Transfer': is_outgoing,
                    'Is Incoming Transfer': is_incoming,
                }
                
                # Add empty columns for all other fields (stats, etc.)
                for col in scraped_df.columns:
                    if col not in new_row:
                        new_row[col] = None
                
                # Append to scraped_df
                scraped_df = pd.concat([scraped_df, pd.DataFrame([new_row])], ignore_index=True)
                manual_updates.append(('added', team, name))
    
    # Now recalculate projected counts for teams with manual data
    # (after all manual updates/additions are done)
    print()
    print('Recalculating projected counts for teams with manual data...')
    
    for team in sorted(manual_teams):
        norm_school = normalize_school_key(team)
        
        # Get all players for this team from updated scraped_df
        team_rows = scraped_df[scraped_df['Team'] == team]
        
        if len(team_rows) == 0:
            continue
        
        # Calculate returning players (not graduating, not transferring out)
        returning_mask = (team_rows['Is Graduating'] != 1) & (team_rows['Is Outgoing Transfer'] != 1)
        returning_players = team_rows[returning_mask]
        
        returning_setters = returning_players[returning_players['Is Setter'] == 1]
        returning_pins = returning_players[returning_players['Is Pin Hitter'] == 1]
        returning_middles = returning_players[returning_players['Is Middle Blocker'] == 1]
        returning_defs = returning_players[returning_players['Is Def Specialist'] == 1]
        
        # Get incoming players for this team from incoming_players list
        team_incoming = [p for p in incoming_players if normalize_school_key(p['school']) == norm_school]
        
        # Categorize incoming players by position
        incoming_setters = []
        incoming_pins = []
        incoming_middles = []
        incoming_defs = []
        for inc in team_incoming:
            pos_codes = extract_position_codes(inc.get('position', ''))
            # Same S/DS rule
            if 'S' in pos_codes and 'DS' not in pos_codes:
                incoming_setters.append(inc)
            if 'OH' in pos_codes or 'RS' in pos_codes:
                incoming_pins.append(inc)
            if 'MB' in pos_codes:
                incoming_middles.append(inc)
            if 'DS' in pos_codes:
                incoming_defs.append(inc)
        
        # Calculate counts
        returning_setter_count = len(returning_setters)
        returning_pin_count = len(returning_pins)
        returning_mb_count = len(returning_middles)
        returning_def_count = len(returning_defs)
        
        incoming_setter_count = len(incoming_setters)
        incoming_pin_count = len(incoming_pins)
        incoming_mb_count = len(incoming_middles)
        incoming_def_count = len(incoming_defs)
        
        projected_setter_count = returning_setter_count + incoming_setter_count
        projected_pin_count = returning_pin_count + incoming_pin_count
        projected_mb_count = returning_mb_count + incoming_mb_count
        projected_def_count = returning_def_count + incoming_def_count
        
        # Format names for display
        def format_player_label(row):
            name = row['Name']
            class_abbr = row.get('Class Next Year', '') or row.get('Class', '')
            return f"{name} ({class_abbr})" if class_abbr else name
        
        def format_incoming_label(p):
            return p['name']
        
        returning_setter_names = ', '.join(format_player_label(row) for _, row in returning_setters.iterrows())
        returning_pin_names = ', '.join(format_player_label(row) for _, row in returning_pins.iterrows())
        returning_mb_names = ', '.join(format_player_label(row) for _, row in returning_middles.iterrows())
        returning_def_names = ', '.join(format_player_label(row) for _, row in returning_defs.iterrows())
        
        incoming_setter_names = ', '.join(format_incoming_label(p) for p in incoming_setters)
        incoming_pin_names = ', '.join(format_incoming_label(p) for p in incoming_pins)
        incoming_mb_names = ', '.join(format_incoming_label(p) for p in incoming_middles)
        incoming_def_names = ', '.join(format_incoming_label(p) for p in incoming_defs)
        
        # Update all rows for this team with calculated counts and names
        team_mask = scraped_df['Team'] == team
        scraped_df.loc[team_mask, 'Returning Setter Count'] = returning_setter_count
        scraped_df.loc[team_mask, 'Returning Pin Hitter Count'] = returning_pin_count
        scraped_df.loc[team_mask, 'Returning Middle Blocker Count'] = returning_mb_count
        scraped_df.loc[team_mask, 'Returning Def Specialist Count'] = returning_def_count
        
        scraped_df.loc[team_mask, 'Incoming Setter Count'] = incoming_setter_count
        scraped_df.loc[team_mask, 'Incoming Pin Hitter Count'] = incoming_pin_count
        scraped_df.loc[team_mask, 'Incoming Middle Blocker Count'] = incoming_mb_count
        scraped_df.loc[team_mask, 'Incoming Def Specialist Count'] = incoming_def_count
        
        scraped_df.loc[team_mask, 'Projected Setter Count'] = projected_setter_count
        scraped_df.loc[team_mask, 'Projected Pin Hitter Count'] = projected_pin_count
        scraped_df.loc[team_mask, 'Projected Middle Blocker Count'] = projected_mb_count
        scraped_df.loc[team_mask, 'Projected Def Specialist Count'] = projected_def_count
        
        scraped_df.loc[team_mask, 'Returning Setters'] = returning_setter_names
        scraped_df.loc[team_mask, 'Returning Pins'] = returning_pin_names
        scraped_df.loc[team_mask, 'Returning Middles'] = returning_mb_names
        scraped_df.loc[team_mask, 'Returning Defs'] = returning_def_names
        
        scraped_df.loc[team_mask, 'Incoming Setters'] = incoming_setter_names
        scraped_df.loc[team_mask, 'Incoming Pins'] = incoming_pin_names
        scraped_df.loc[team_mask, 'Incoming Middles'] = incoming_mb_names
        scraped_df.loc[team_mask, 'Incoming Defs'] = incoming_def_names
    
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
