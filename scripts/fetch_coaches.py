#!/usr/bin/env python3
"""
Fetch and cache coaching staff data for all D1 volleyball teams.

This script scrapes coaching information (name, title, email, phone) from team
websites and stores it in a JSON cache file. The cache can then be used by
create_team_pivot_csv.py to avoid re-fetching coach data on every run.

Usage:
    python scripts/fetch_coaches.py
    python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas"
    python scripts/fetch_coaches.py --output settings/coaches_cache_2026.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.teams_loader import load_teams
from scraper.coaches import find_coaches_page_url, parse_coaches_from_html
from scraper.utils import fetch_html, normalize_school_key
from scraper.logging_utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

DEFAULT_CACHE_FILE = "settings/coaches_cache.json"


def fetch_coaches_for_team(team_info: dict, fetch_tenure: bool = False) -> list:
    """
    Fetch coaching staff data for a single team.
    
    Args:
        team_info: Dict with 'team', 'url', etc.
        fetch_tenure: If True, fetch individual bio pages to estimate start year / seasons.
        
    Returns:
        List of coach dicts: [{"name": ..., "title": ..., "email": ..., "phone": ...}]
    """
    team_name = team_info["team"]
    roster_url = team_info.get("url", "")
    
    if not roster_url:
        logger.warning(f"No roster URL for {team_name}")
        return []
    
    try:
        # Fetch roster page
        logger.info(f"Fetching coaches for: {team_name}")
        roster_html = fetch_html(roster_url)
        
        # Try to find dedicated coaches page
        coaches_html = roster_html
        alt_coaches_url = find_coaches_page_url(roster_html, roster_url)
        
        if alt_coaches_url:
            try:
                logger.debug(f"  Fetching coaches page: {alt_coaches_url}")
                coaches_html = fetch_html(alt_coaches_url)
            except Exception as e:
                logger.warning(f"  Could not fetch coaches page URL, using roster: {e}")
        
        # Parse coaches from HTML
        coaches = parse_coaches_from_html(
            coaches_html,
            base_url=alt_coaches_url or roster_url,
            fetch_bios=fetch_tenure,
        )
        
        if coaches:
            logger.info(f"  Found {len(coaches)} coach(es)")
            for coach in coaches:
                logger.debug(f"    - {coach['name']} ({coach['title']})")
        else:
            logger.warning(f"  No coaches found for {team_name}")
        
        return coaches
        
    except Exception as e:
        logger.error(f"Error fetching coaches for {team_name}: {e}")
        return []


def load_cache(cache_file: str) -> dict:
    """Load existing cache file if it exists."""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded existing cache with {len(data.get('teams', {}))} teams")
                return data
        except Exception as e:
            logger.warning(f"Could not load cache file: {e}")
    
    return {"generated_at": None, "teams": {}}


def save_cache(cache_file: str, cache_data: dict):
    """Save cache data to JSON file."""
    os.makedirs(os.path.dirname(cache_file) or ".", exist_ok=True)
    
    cache_data["generated_at"] = datetime.now().isoformat()
    
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved cache to: {cache_file}")


def main():
    parser = argparse.ArgumentParser(description="Fetch and cache coaching staff data")
    parser.add_argument(
        "--output",
        default=DEFAULT_CACHE_FILE,
        help=f"Output cache file (default: {DEFAULT_CACHE_FILE})"
    )
    parser.add_argument(
        "--teams",
        nargs="+",
        help="Only fetch coaches for specific teams (by name)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh all teams (ignore existing cache)"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update cache (only fetch teams not in cache)"
    )
    parser.add_argument(
        "--tenure",
        action="store_true",
        help="Fetch coach bio pages to estimate start year and seasons at school"
    )
    
    args = parser.parse_args()
    
    cache_file = args.output
    
    # Load existing cache
    if args.refresh:
        logger.info("Refreshing all teams (ignoring existing cache)")
        cache_data = {"generated_at": None, "teams": {}}
    else:
        cache_data = load_cache(cache_file)
    
    # Determine which teams to fetch
    if args.teams:
        # Filter to specific teams
        team_names_normalized = {normalize_school_key(t) for t in args.teams}
        teams_to_fetch = [
            t for t in load_teams()
            if normalize_school_key(t["team"]) in team_names_normalized
        ]
        logger.info(f"Fetching {len(teams_to_fetch)} specified team(s)")
    else:
        teams_to_fetch = load_teams()
        logger.info(f"Fetching all {len(teams_to_fetch)} D1 teams")
    
    # Filter out teams already in cache (if --update mode)
    if args.update:
        cached_teams = set(cache_data["teams"].keys())
        teams_to_fetch = [
            t for t in teams_to_fetch
            if t["team"] not in cached_teams
        ]
        logger.info(f"Update mode: {len(teams_to_fetch)} teams not in cache")
    
    if not teams_to_fetch:
        logger.info("No teams to fetch")
        return
    
    # Fetch coaches for each team
    success_count = 0
    error_count = 0
    
    for i, team_info in enumerate(teams_to_fetch, 1):
        team_name = team_info["team"]
        logger.info(f"[{i}/{len(teams_to_fetch)}] Processing: {team_name}")
        
        coaches = fetch_coaches_for_team(team_info, fetch_tenure=args.tenure)
        
        if coaches:
            cache_data["teams"][team_name] = {
                "coaches": coaches,
                "fetched_at": datetime.now().isoformat(),
                "roster_url": team_info.get("url", ""),
            }
            success_count += 1
        else:
            # Store empty list so we don't keep trying
            cache_data["teams"][team_name] = {
                "coaches": [],
                "fetched_at": datetime.now().isoformat(),
                "roster_url": team_info.get("url", ""),
            }
            error_count += 1
    
    # Save updated cache
    save_cache(cache_file, cache_data)
    
    print()
    print("=" * 80)
    print(f"Fetch complete:")
    print(f"  Success: {success_count} teams")
    print(f"  No coaches found: {error_count} teams")
    print(f"  Total in cache: {len(cache_data['teams'])} teams")
    print(f"  Cache file: {cache_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
