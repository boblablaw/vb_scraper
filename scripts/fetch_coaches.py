#!/usr/bin/env python3
"""
Fetch coaching staff data for each team and write it directly into settings/teams.json.

 - Scrapes coaching information (name, title, email, phone) from team roster/coaches pages.
 - Updates the "coaches" array for each team in teams.json.
 - Existing coaches entries are replaced only when new data is found; otherwise they are left intact.

Usage:
    python scripts/fetch_coaches.py
    python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas"
    python scripts/fetch_coaches.py --teams-json settings/teams.json
    python scripts/fetch_coaches.py --tenure   # also fetches bio pages for tenure info
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.helpers.teams_loader import load_teams
from scripts.helpers.coaches import find_coaches_page_url, parse_coaches_from_html
from scripts.helpers.utils import fetch_html, normalize_school_key, normalize_text
from scripts.helpers.logging_utils import setup_logging, get_logger
import requests

setup_logging()
logger = get_logger(__name__)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
COACH_PHOTOS_DIR = ASSETS_DIR / "coaches_photos"
COACH_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
VALID_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _slugify_filename(value: str) -> str:
    text = normalize_text(value)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "coach"


def _download_coach_photo(team_name: str, coach_name: str, photo_url: str) -> str:
    if not photo_url:
        return ""

    filename_base = f"{_slugify_filename(team_name)}_{_slugify_filename(coach_name)}"
    parsed = urlsplit(photo_url)
    ext = Path(parsed.path).suffix.lower()
    if ext not in VALID_PHOTO_EXTS:
        ext = ".jpg"

    filename = f"{filename_base}{ext}"
    dest = COACH_PHOTOS_DIR / filename
    if dest.exists():
        return f"assets/coaches_photos/{filename}"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; coaches-photo-fetcher/1.0)"}
    try:
        resp = requests.get(photo_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to download coach photo for %s (%s): %s", coach_name, team_name, exc)
        return ""

    try:
        dest.write_bytes(resp.content)
        logger.info("Saved coach photo for %s to %s", coach_name, dest)
        return f"assets/coaches_photos/{filename}"
    except Exception as exc:
        logger.warning("Could not write coach photo to %s: %s", dest, exc)
        return ""


def _attach_coach_photo(team_name: str, coach: dict) -> None:
    photo_url = (coach.pop("photo_url", "") or "").strip()
    if not photo_url:
        return
    photo_path = _download_coach_photo(team_name, coach.get("name", "coach"), photo_url)
    if photo_path:
        coach["coach_photo"] = photo_path


DEFAULT_TEAMS_JSON = Path(__file__).resolve().parent.parent / "settings" / "teams.json"


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
                coach.setdefault("coach_photo", "")
                _attach_coach_photo(team_name, coach)
                logger.debug(f"    - {coach['name']} ({coach['title']})")
        else:
            logger.warning(f"  No coaches found for {team_name}")
        
        return coaches
        
    except Exception as e:
        logger.error(f"Error fetching coaches for {team_name}: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Fetch coaching staff data and populate teams.json")
    parser.add_argument(
        "--teams",
        nargs="+",
        help="Only fetch coaches for specific teams (by name)"
    )
    parser.add_argument(
        "--tenure",
        action="store_true",
        help="Fetch coach bio pages to estimate start year and seasons at school"
    )
    parser.add_argument(
        "--teams-json",
        type=Path,
        default=DEFAULT_TEAMS_JSON,
        help="Path to teams.json to read/write (default: settings/teams.json)",
    )
    
    args = parser.parse_args()
    
    # Determine which teams to fetch
    if args.teams:
        # Filter to specific teams
        team_names_normalized = {normalize_school_key(t) for t in args.teams}
        teams_data = [t for t in load_teams(args.teams_json) if normalize_school_key(t["team"]) in team_names_normalized]
        logger.info(f"Fetching {len(teams_data)} specified team(s)")
    else:
        teams_data = load_teams(args.teams_json)
        logger.info(f"Fetching all {len(teams_data)} D1 teams")

    teams_to_fetch = teams_data

    if not teams_to_fetch:
        logger.info("No teams to fetch")
        return
    
    # Fetch coaches for each team
    success_count = 0
    error_count = 0
    fetched_map = {}

    for i, team_info in enumerate(teams_to_fetch, 1):
        team_name = team_info["team"]
        logger.info(f"[{i}/{len(teams_to_fetch)}] Processing: {team_name}")
        
        coaches = fetch_coaches_for_team(team_info, fetch_tenure=args.tenure)
        
        if coaches:
            # Ensure coach_photo key exists for downstream use
            for c in coaches:
                c.setdefault("coach_photo", "")
            fetched_map[normalize_school_key(team_name)] = coaches
            success_count += 1
        else:
            error_count += 1

    # Update teams.json with fetched coaches (replace only if we found data)
    updated = 0
    for team in teams_data:
        key = normalize_school_key(team.get("team", ""))
        if key in fetched_map:
            team["coaches"] = fetched_map[key]
            updated += 1

    try:
        args.teams_json.parent.mkdir(parents=True, exist_ok=True)
        args.teams_json.write_text(json.dumps(teams_data, indent=2, ensure_ascii=False))
        logger.info(f"Updated coaches for {updated} team(s) in {args.teams_json}")
    except Exception as exc:
        logger.error(f"Failed to write teams JSON: {exc}")
    
    print()
    print("=" * 80)
    print(f"Fetch complete:")
    print(f"  Success: {success_count} teams")
    print(f"  No coaches found: {error_count} teams")
    print(f"  Teams updated: {updated}")
    print(f"  Teams file: {args.teams_json}")
    print("=" * 80)


if __name__ == "__main__":
    main()
