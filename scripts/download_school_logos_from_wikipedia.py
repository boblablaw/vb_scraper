#!/usr/bin/env python3
"""
download_commons_logos_from_wikipedia.py
----------------------------------------
Fetch athletic-style logos for all NCAA Division I women's volleyball programs.

What it does:
1. Scrapes the Wikipedia page:
   "List of NCAA Division I women's volleyball programs"
2. Extracts the list of schools from the 'School' column.
3. For each school, queries Wikimedia Commons for a '<school> logo'.
4. Picks the best candidate (prefers SVG, 'logo' in title, athletics marks).
5. Downloads the image into a local /logos folder.
6. Writes commons_logos_d1_from_wikipedia.csv with metadata.

Requirements:
    pip install pandas requests lxml
"""

import os
import re
import csv
import time
import sys
import argparse
import html
from pathlib import Path
from io import StringIO
import requests
import pandas as pd

# Ensure project modules are importable when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.utils import normalize_school_key
from settings.teams import TEAMS

# ---------------- CONFIG ----------------

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_NCAA_Division_I_women%27s_volleyball_programs"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

OUTPUT_CSV = "commons_logos_d1_from_wikipedia.csv"
LOGO_DIR = "logos"
os.makedirs(LOGO_DIR, exist_ok=True)
MISSING_LOGOS_PATH = os.path.join(LOGO_DIR, "missing_school_logos.txt")
TEAM_URLS = {normalize_school_key(t["team"]): t.get("url") for t in TEAMS}

REQUEST_DELAY = 0.4  # seconds between Commons API calls
DEFAULT_HEADERS = {
    # Wikipedia blocks generic Python UA; use a descriptive one instead.
    "User-Agent": "vb-scraper/1.0 (https://github.com/jasonbeatty/vb_scraper)"
}


# ---------------- HELPERS ----------------

def slugify(name: str) -> str:
    """Turn school name into a safe filename."""
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name)


def get_d1_volleyball_schools() -> list[str]:
    """
    Scrape Wikipedia 'List of NCAA Division I women's volleyball programs'
    and return a list of school names from the 'School' column.
    """
    print(f"Fetching school list from Wikipedia: {WIKI_URL}")
    try:
        resp = requests.get(WIKI_URL, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Wikipedia page: {e}")

    tables = pd.read_html(StringIO(resp.text))  # requires lxml

    target = None
    for df in tables:
        cols = [c.lower() for c in df.columns]
        if "school" in cols:
            target = df
            break

    if target is None:
        raise RuntimeError("Could not find a table with a 'School' column on the Wikipedia page.")

    # Normalize column name
    # (handles cases where col might be 'School ' or similar)
    for c in target.columns:
        if str(c).strip().lower() == "school":
            school_col = c
            break

    schools = (
        target[school_col]
        .astype(str)
        .str.strip()
        .replace("nan", pd.NA)
        .dropna()
        .unique()
    )

    schools = [s for s in schools if s and s != "School"]
    print(f"Found {len(schools)} schools on the Wikipedia page.")
    return sorted(schools)


def search_commons_for_logo(query_str: str, limit: int = 15) -> dict | None:
    """
    Query Wikimedia Commons for an image related to the given query string.
    Returns a dict with 'title', 'url', 'mime', 'score' OR None if no good match.
    """
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query_str,
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": "1024",
        "iiurlheight": "1024",
        "gsrnamespace": "6",  # File namespace (images)
    }

    try:
        resp = requests.get(COMMONS_API, params=params, timeout=15, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ERROR: Commons API request failed for '{query_str}': {e}")
        return None

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    candidates = []
    for _, page in pages.items():
        title = page.get("title", "")
        if not title.lower().startswith("file:"):
            continue

        ii_list = page.get("imageinfo", [])
        if not ii_list:
            continue

        ii = ii_list[0]
        url = ii.get("url")
        mime = ii.get("mime", "")

        if not url:
            continue

        lt = title.lower()
        score = 0
        if "logo" in lt:
            score += 5
        if lt.endswith(".svg"):
            score += 3
        if "athletic" in lt or "athletics" in lt:
            score += 2
        if "wordmark" in lt:
            score += 1

        candidates.append({
            "title": title,
            "url": url,
            "mime": mime,
            "score": score
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0]
    if best["score"] <= 0:
        return None
    return best


def nickname_query_for_team(team_name: str) -> str | None:
    """
    Optional: small dictionary of nickname-based queries for tougher schools.
    You can expand this mapping as needed.
    """
    mapping = {
        "Iowa State University": "Iowa State Cyclones logo",
        "Kansas State University": "Kansas State Wildcats logo",
        "University of Utah": "Utah Utes logo",
        "Florida State University": "Florida State Seminoles logo",
        "University of Connecticut": "UConn Huskies logo",
        "Boise State University": "Boise State Broncos logo",
        "University of Denver": "Denver Pioneers logo",
        "Northern Arizona University": "NAU Lumberjacks logo",
        "University of Illinois Chicago": "UIC Flames logo",
        "UMBC": "UMBC Retrievers logo",
    }
    return mapping.get(team_name)


def download_logo(team_name: str, url: str) -> str:
    """
    Download image from `url` and save it as /logos/<team>.<ext>
    Returns the local file path (or "" on failure).
    """
    url = clean_image_url(url)
    ext = os.path.splitext(url)[1]
    if not ext:
        ext = ".png"

    filename = slugify(team_name) + ext
    filepath = os.path.join(LOGO_DIR, filename)

    try:
        r = requests.get(url, timeout=20, headers=DEFAULT_HEADERS)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        return filepath
    except Exception as e:
        print(f"  ERROR downloading logo for {team_name}: {e}")
        return ""


def find_existing_logo(team_name: str) -> str:
    """Return path to an existing logo file for team if present (ignores *_BAD files), else ''."""
    slug = slugify(team_name)
    for fname in os.listdir(LOGO_DIR):
        name, _ext = os.path.splitext(fname)
        if name == slug:
            return os.path.join(LOGO_DIR, fname)
    return ""


def has_bad_logo_marker(team_name: str) -> bool:
    """
    Detect if a previous logo was marked bad by suffixing filename with '_BAD'.
    This signals we should try fallback sources instead of skipping.
    """
    slug = slugify(team_name)
    for fname in os.listdir(LOGO_DIR):
        name, _ext = os.path.splitext(fname)
        if name == f"{slug}_BAD":
            return True
    return False


def lookup_team_roster_url(team_name: str) -> str:
    """Return roster URL from settings.TEAMS using normalized name matching."""
    key = normalize_school_key(team_name)
    return TEAM_URLS.get(key) or ""


def extract_og_image(html: str) -> str:
    """
    Try to pull a logo-like image from meta tags (og:image / twitter:image).
    This is a lightweight regex instead of a full HTML parser.
    """
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def extract_header_logo(html: str) -> str:
    """
    Some sites keep a header logo on the page with classes like
    'main-header__logo-image' (Cleveland State) or 'main-logo' (Bryant).
    Grab that src/data-src/srcset.
    """
    class_patterns = [
        "main-header__logo-image",  # Cleveland State
        "main-logo",                # Bryant
        "main-logo-1",              # Campbell variant
        "primary",                  # Belmont Sidearm header mark
    ]
    for cls in class_patterns:
        img_match = re.search(fr'<img[^>]+class="[^">]*{re.escape(cls)}[^">]*"[^>]*>', html, re.IGNORECASE)
        if not img_match:
            continue
        tag = img_match.group(0)
        # Prefer src, then data-src, then first entry in srcset
        for attr in ("src", "data-src"):
            m = re.search(fr'{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        m = re.search(r'srcset=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if m:
            first = m.group(1).split(",")[0].strip().split()[0]
            return first
    # Belmont: logo wrapped in a div.main_header__logo with img.primary
    container = re.search(r'<div[^>]+class="[^">]*main_header__logo[^">]*"[^>]*>(.*?)</div>', html, re.IGNORECASE | re.DOTALL)
    if container:
        inner = container.group(1)
        img_match = re.search(r'<img[^>]+class="[^">]*primary[^">]*"[^>]*>', inner, re.IGNORECASE)
        if img_match:
            tag = img_match.group(0)
            for attr in ("src", "data-src"):
                m = re.search(fr'{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            m = re.search(r'srcset=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if m:
                first = m.group(1).split(",")[0].strip().split()[0]
                return first
    return ""


def clean_image_url(url: str) -> str:
    """Decode HTML entities and strip whitespace; also normalize // to https://."""
    if not url:
        return ""
    url = html.unescape(url).strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def fetch_team_site_logo_url(team_name: str) -> str:
    """
    Fallback: fetch roster page and grab og:image/twitter:image as a logo candidate.
    """
    roster_url = lookup_team_roster_url(team_name)
    if not roster_url:
        print("  No roster URL mapping found for this team; skipping team-site fallback.")
        return ""

    try:
        resp = requests.get(roster_url, headers=DEFAULT_HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching team site for fallback: {e}")
        return ""

    html = resp.text
    # Try meta tags first, then header logo pattern.
    logo_url = clean_image_url(extract_og_image(html))
    # Some Sidearm sites expose an image-proxy convert URL that may 400; prefer direct header logo if present.
    if (not logo_url) or ("sidearmdev.com/convert" in logo_url):
        header_logo = clean_image_url(extract_header_logo(html))
        if header_logo:
            logo_url = header_logo
    if not logo_url:
        print("  No og:image/twitter:image or header logo found on roster page.")
        return ""

    return logo_url


# ---------------- MAIN ----------------

def main(selected_teams: list[str] | None = None):
    # Step 1: get all D1 volleyball schools from Wikipedia
    schools = get_d1_volleyball_schools()
    if selected_teams:
        wanted = {normalize_school_key(t) for t in selected_teams}
        schools = [s for s in schools if normalize_school_key(s) in wanted]
        print(f"Filtering to {len(schools)} selected team(s).")

    rows_out = []
    missing_logos = []

    for i, school in enumerate(schools, start=1):
        print(f"[{i}/{len(schools)}] {school}")

        # Skip network work if we already have a logo file locally.
        existing = find_existing_logo(school)
        bad_marker_present = has_bad_logo_marker(school)
        if existing and not bad_marker_present:
            print(f"  ✅ Already have logo at {existing}, skipping download.")
            rows_out.append({
                "team": school,
                "commons_page_title": "",
                "image_url": "",
                "mime_type": "",
                "score": 0,
                "source": "existing_file",
                "local_file": existing
            })
            continue

        if bad_marker_present:
            print("  ⚠️  Found *_BAD marker; will attempt fallback download.")

        # First attempt: direct "<school> logo"
        search_query = f'"{school}" logo'
        best = search_commons_for_logo(search_query)
        source = "direct"

        # Second attempt: nickname-based query
        if not best:
            nick_query = nickname_query_for_team(school)
            if nick_query:
                print(f"  No direct hit; trying nickname query: {nick_query}")
                best = search_commons_for_logo(nick_query)
                source = "nickname"

        # Fallback to team site if Commons failed or a BAD marker was placed.
        if bad_marker_present or not best:
            fallback_url = fetch_team_site_logo_url(school)
            if fallback_url:
                best = {
                    "title": "Team site og:image",
                    "url": fallback_url,
                    "mime": "",
                    "score": 0
                }
                source = "team_site"
                print("  ✔ Found fallback logo from team site.")
            elif bad_marker_present:
                print("  Team-site fallback failed despite BAD marker; will use Commons result if available.")

        # Record result
        if not best:
            print("  ❌ No good logo found.")
            missing_logos.append(school)
            rows_out.append({
                "team": school,
                "commons_page_title": "",
                "image_url": "",
                "mime_type": "",
                "score": 0,
                "source": "not_found",
                "local_file": ""
            })
        else:
            print(f"  ✔ Found: {best['title']} ({best['mime']})")
            local_path = download_logo(school, best["url"])
            rows_out.append({
                "team": school,
                "commons_page_title": best["title"],
                "image_url": best["url"],
                "mime_type": best["mime"],
                "score": best["score"],
                "source": source,
                "local_file": local_path
            })

        time.sleep(REQUEST_DELAY)

    # Step 3: write metadata CSV
    fieldnames = [
        "team", "commons_page_title", "image_url",
        "mime_type", "score", "source", "local_file"
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    # Write missing logos list for manual follow-up
    if missing_logos:
        with open(MISSING_LOGOS_PATH, "w", encoding="utf-8") as f:
            f.write("Schools without a found Commons logo\n")
            for name in missing_logos:
                f.write(f"- {name}\n")
        print(f"Missing logos written to: {MISSING_LOGOS_PATH}")

    print("\nDone.")
    print(f"Logos saved into: {LOGO_DIR}")
    print(f"Metadata written to: {OUTPUT_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download D1 volleyball logos from Wikimedia Commons with team-site fallbacks.")
    parser.add_argument("--team", action="append", help="Restrict to specific team(s); can be provided multiple times.")
    args = parser.parse_args()

    main(selected_teams=args.team)
