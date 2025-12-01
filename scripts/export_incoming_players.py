#!/usr/bin/env python3
"""
Export incoming players data to CSV format.

Allows specifying which year's data to export via command line arguments.
"""

import argparse
import csv
import sys
import os
from datetime import datetime

# Add parent directory to path to import settings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.incoming_players import parse_raw_incoming_players


def get_incoming_players_for_year(year):
    """
    Load incoming players data for a specific year.
    
    Args:
        year: The year to load data for (e.g., 2025, 2026)
        
    Returns:
        str: Raw incoming text for the specified year
    """
    try:
        import importlib
        module_name = f'incoming_players_data_{year}'
        module = importlib.import_module(f'settings.{module_name}')
        raw_text = getattr(module, f'RAW_INCOMING_TEXT_{year}')
        return raw_text
    except (ImportError, AttributeError) as e:
        print(f"Error: Could not load incoming players data for {year}", file=sys.stderr)
        print(f"Make sure settings/incoming_players_data_{year}.py exists", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)


def export_to_csv(players, output_file):
    """
    Export players list to CSV file.
    
    Args:
        players: List of player dicts with keys: conference, school, name, position, club
        output_file: Path to output CSV file
    """
    if not players:
        print("Warning: No players to export", file=sys.stderr)
        return
    
    fieldnames = ['conference', 'school', 'name', 'position', 'club']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(players)
    
    print(f"✓ Exported {len(players)} players to {output_file}")


def get_current_year():
    """Get the year that would be automatically selected."""
    from settings.incoming_players_data import get_incoming_players_year
    return get_incoming_players_year()


def main():
    parser = argparse.ArgumentParser(
        description='Export incoming players data to CSV format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export current year's data (auto-selected based on date)
  python scripts/export_incoming_players.py
  
  # Export specific year's data
  python scripts/export_incoming_players.py --year 2026
  
  # Export to custom file
  python scripts/export_incoming_players.py --year 2025 --output data/incoming_2025.csv
  
  # List available years
  python scripts/export_incoming_players.py --list

Available years are determined by which incoming_players_data_YYYY.py files exist
in the settings/ directory.
        """
    )
    
    parser.add_argument(
        '--year',
        type=int,
        help='Year of incoming players data to export (e.g., 2025, 2026). If not specified, uses current year based on date.'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output CSV file path (default: exports/incoming_players_YYYY.csv)'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available incoming players data files'
    )
    
    args = parser.parse_args()
    
    # Handle --list
    if args.list:
        import glob
        files = glob.glob('settings/incoming_players_data_*.py')
        files = [f for f in files if f != 'settings/incoming_players_data.py']  # Exclude selector
        
        if files:
            print("Available incoming players data files:")
            for f in sorted(files):
                year = f.replace('settings/incoming_players_data_', '').replace('.py', '')
                print(f"  - {year}")
            
            current = get_current_year()
            print(f"\nCurrent year (auto-selected): {current}")
        else:
            print("No incoming players data files found")
        return
    
    # Determine year to use
    if args.year:
        year = args.year
        print(f"Using specified year: {year}")
    else:
        year = get_current_year()
        print(f"Using current year (auto-selected): {year}")
    
    # Determine output file
    if args.output:
        output_file = args.output
    else:
        os.makedirs('exports', exist_ok=True)
        output_file = f'exports/incoming_players_{year}.csv'
    
    # Load data
    print(f"Loading incoming players data for {year}...")
    raw_text = get_incoming_players_for_year(year)
    
    # Parse data
    print("Parsing incoming players...")
    players = parse_raw_incoming_players(raw_text)
    
    if not players:
        print("Warning: No players parsed from data", file=sys.stderr)
        print("The data file may be empty or improperly formatted", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(players)} players")
    
    # Show summary by conference
    conferences = {}
    for p in players:
        conf = p['conference']
        if conf not in conferences:
            conferences[conf] = 0
        conferences[conf] += 1
    
    print(f"\nBreakdown by conference:")
    for conf, count in sorted(conferences.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {conf}: {count} players")
    if len(conferences) > 5:
        print(f"  ... and {len(conferences) - 5} more conferences")
    
    # Export to CSV
    print(f"\nExporting to {output_file}...")
    export_to_csv(players, output_file)
    
    print(f"\n✓ Success! Data exported to {output_file}")


if __name__ == '__main__':
    main()
