#!/usr/bin/env python3
"""
Fetch missing player photos using team roster pages.

This script:
 - Reads a merged roster/stats CSV (default: exports/ncaa_wvb_merged_2025.csv).
 - Identifies players without an existing photo in assets/player_photos/.
 - Visits each team's roster URL (from settings/teams.json) with Playwright.
 - Attempts to locate the player's headshot on the page and download it.
 - Writes a CSV of players still missing photos.

Usage example:
    python scripts/fetch_missing_player_photos.py \
        --input exports/ncaa_wvb_merged_2025.csv \
        --output-dir assets/player_photos \
        --missing-output exports/missing_player_photos_after_fetch.csv \
        --headed
"""

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT_DIR / "scripts" / "ncaa_wvb_rosters_d1_2025.csv"
PHOTOS_DIR = ROOT_DIR / "assets" / "player_photos"
TEAMS_JSON = ROOT_DIR / "settings" / "teams.json"
DEFAULT_MISSING_OUTPUT = ROOT_DIR / "exports" / "missing_player_photos_after_fetch.csv"


def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def build_team_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Returns (alias->canonical_slug, canonical_slug->roster_url)."""
    aliases: dict[str, str] = {}
    roster_urls: dict[str, str] = {}
    if not TEAMS_JSON.exists():
        return aliases, roster_urls
    try:
        teams = json.loads(TEAMS_JSON.read_text())
        for t in teams:
            canonical = t.get("team") or t.get("short_name") or ""
            canonical_slug = slugify(canonical)
            if canonical_slug:
                roster_urls[canonical_slug] = t.get("url") or ""
            for alias in [canonical] + (t.get("team_name_aliases") or []):
                if alias:
                    aliases[alias.lower()] = canonical_slug
    except Exception:
        aliases, roster_urls = {}, {}
    return aliases, roster_urls


def build_photo_index(photos_dir: Path) -> dict[str, str]:
    photo_index: dict[str, str] = {}
    if not photos_dir.exists():
        return photo_index
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"):
        for p in photos_dir.glob(ext):
            photo_index[p.name.lower()] = p.name
    return photo_index


def find_existing_photo(team: str, player: str, photo_index: dict[str, str], team_aliases: dict[str, str]) -> str:
    if not photo_index:
        return ""
    team_lookup = team_aliases.get(team.lower(), team)
    team_key = slugify(team_lookup)
    player_key = slugify(player)
    if not team_key or not player_key:
        return ""

    base = f"{team_key}_{player_key}".lower()
    for ext in (".jpg", ".jpeg", ".png"):
        fname = base + ext
        if fname in photo_index:
            return photo_index[fname]

    for suffix in ("_university", "_college"):
        for ext in (".jpg", ".jpeg", ".png"):
            fname = (team_key + suffix + f"_{player_key}").lower() + ext
            if fname in photo_index:
                return photo_index[fname]

    for fname, original in photo_index.items():
        if team_key in fname and player_key in fname:
            return original
    return ""


def choose_best_image(candidates: Iterable[dict], player: str) -> Optional[str]:
    """Pick the best image URL from a list of {src, alt, aria} dicts."""
    player_tokens = [t for t in re.split(r"\\s+", player.lower()) if t]
    best = None
    for c in candidates:
        src = c.get("src") or ""
        alt = (c.get("alt") or "") + " " + (c.get("aria") or "")
        alt_l = alt.lower()
        if player_tokens and all(tok in alt_l for tok in player_tokens):
            best = src
            break
        if not best and alt_l and any(tok in alt_l for tok in player_tokens):
            best = src
    return best


def fetch_photo_for_player(page, base_url: str, player: str) -> Optional[str]:
    """
    Attempt to locate the player's image on the current page.
    Returns the absolute image URL if found.
    """
    # Collect all images with their alt/aria text
    images = page.eval_on_selector_all(
        "img",
        "els => els.map(e => ({src: e.src, alt: e.alt || '', aria: e.getAttribute('aria-label') || ''}))",
    )
    candidate = choose_best_image(images, player)
    if candidate:
        return urljoin(base_url, candidate)

    # Fallback: look for elements containing the player's name and then grab nearest img ancestor/descendant
    locator = page.locator(f"text=/{re.escape(player)}/i")
    if locator.count() > 0:
        handle = locator.nth(0)
        # Try descendant images first
        desc_img = handle.locator("img")
        if desc_img.count() > 0:
            src = desc_img.first.get_attribute("src") or ""
            if src:
                return urljoin(base_url, src)
        # Try ancestor images
        ancestor_img = handle.locator("xpath=ancestor::*//img")
        if ancestor_img.count() > 0:
            src = ancestor_img.first.get_attribute("src") or ""
            if src:
                return urljoin(base_url, src)
    return None


def download_image(context, url: str, dest: Path) -> bool:
    if not url:
        return False
    try:
        resp = context.request.get(url)
        if not resp.ok:
            return False
        dest.write_bytes(resp.body())
        return True
    except Exception:
        return False


def process_missing_photos(
    input_csv: Path,
    photos_dir: Path,
    missing_output: Path,
    headless: bool,
    user_agent: str,
    limit: Optional[int] = None,
) -> None:
    df = pd.read_csv(input_csv)
    team_aliases, roster_urls = build_team_maps()
    photo_index = build_photo_index(photos_dir)

    missing_rows = []
    for _, row in df.iterrows():
        team = str(row.get("School") or row.get("Team") or row.get("team") or "")
        player = str(row.get("Player") or row.get("name") or "")
        existing = find_existing_photo(team, player, photo_index, team_aliases)
        if not existing:
            missing_rows.append(
                {
                    "Team": team,
                    "Player": player,
                    "PlayerID": row.get("PlayerID", ""),
                    "TeamID": row.get("TeamID", ""),
                }
            )

    if limit:
        missing_rows = missing_rows[:limit]

    if not missing_rows:
        print("All players already have photos.")
        return

    photos_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()

        still_missing = []
        for idx, rec in enumerate(missing_rows, start=1):
            team = rec["Team"]
            player = rec["Player"]
            canonical_slug = team_aliases.get(team.lower(), slugify(team))
            roster_url = roster_urls.get(canonical_slug, "")

            print(f"[{idx}/{len(missing_rows)}] {team} - {player} ", end="", flush=True)
            if not roster_url:
                print("(no roster URL)")
                still_missing.append(rec)
                continue

            try:
                page.goto(roster_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as exc:
                print(f"(failed to load roster: {exc})")
                still_missing.append(rec)
                continue

            img_url = fetch_photo_for_player(page, page.url, player)
            if not img_url:
                print("(image not found)")
                still_missing.append(rec)
                continue

            ext = Path(urlparse(img_url).path).suffix or ".jpg"
            filename = f"{canonical_slug}_{slugify(player)}{ext}".lower()
            dest = photos_dir / filename
            success = download_image(context, img_url, dest)
            if success:
                print(f"-> saved {filename}")
                photo_index[filename] = filename
            else:
                print("(download failed)")
                still_missing.append(rec)

        browser.close()

    if still_missing:
        pd.DataFrame(still_missing).to_csv(missing_output, index=False)
        print(f"Wrote {len(still_missing)} still-missing photos to {missing_output}")
    else:
        print("Fetched photos for all missing players.")


def main():
    parser = argparse.ArgumentParser(description="Fetch missing player photos using Playwright.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Roster CSV to audit (default: scripts/ncaa_wvb_rosters_d1_2025.csv)")
    parser.add_argument("--output-dir", type=Path, default=PHOTOS_DIR, help="Directory to save photos (default: assets/player_photos)")
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING_OUTPUT, help="CSV listing players still missing after fetch")
    parser.add_argument("--headed", action="store_true", help="Run Playwright headed (default headless)")
    parser.add_argument("--user-agent", type=str, default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", help="User-Agent for requests/browser context")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of missing players to attempt")
    args = parser.parse_args()

    process_missing_photos(
        input_csv=args.input,
        photos_dir=args.output_dir,
        missing_output=args.missing_output,
        headless=not args.headed,
        user_agent=args.user_agent,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
