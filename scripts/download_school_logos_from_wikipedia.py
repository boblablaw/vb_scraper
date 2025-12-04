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
import base64
from pathlib import Path
from io import StringIO
from urllib.parse import urlsplit, parse_qs, unquote
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
TEAM_LOGO_OVERRIDES = {
    # Auburn inline SVG header logo (provided sample)
    normalize_school_key("Auburn University"): "data:image/svg+xml,%3c?xml%20version='1.0'%20encoding='UTF-8'%20standalone='no'?%3e%3csvg%20xmlns:dc='http://purl.org/dc/elements/1.1/'%20xmlns:cc='http://creativecommons.org/ns%23'%20xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns%23'%20xmlns:svg='http://www.w3.org/2000/svg'%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20641%20564.98669'%20height='564.98669'%20width='641'%20xml:space='preserve'%20id='svg2'%20version='1.1'%3e%3cmetadata%20id='metadata8'%3e%3crdf:RDF%3e%3ccc:Work%20rdf:about=''%3e%3cdc:format%3eimage/svg+xml%3c/dc:format%3e%3cdc:type%20rdf:resource='http://purl.org/dc/dcmitype/StillImage'%20/%3e%3c/cc:Work%3e%3c/rdf:RDF%3e%3c/metadata%3e%3cdefs%20id='defs6'%20/%3e%3cg%20transform='matrix(1.3333333,0,0,-1.3333333,0,564.98667)'%20id='g10'%3e%3cg%20transform='scale(0.1)'%20id='g12'%3e%3cpath%20id='path14'%20style='fill:%23f1511b;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='m%203659.99,2999.61%20v%20-209.75%20l%20-104.39,209.75%20h%20104.39%20m%20-2504.39,0%20H%201260%20l%20-104.4,-209.75%20v%20209.75%20M%202403.75,765.422%20c%20-618.49,0%20-820.64,85.719%20-1038.7,206.867%20-18.18,10.102%20-34.33,20.191%20-49.54,30.261%20h%20647.29%20v%20680.32%20H%201569%20l%20174.72,310.61%20h%201368.04%20l%20177.07,-319.74%20h%20-442.68%20v%20-671.19%20h%20645.83%20C%203476.75,992.48%203460.6,982.391%203442.41,972.289%203224.37,851.141%203022.23,765.422%202403.75,765.422%20m%2021.88,2437.668%20295.77,-520.24%20h%20-595.83%20z%20m%202381.86,-203.13%20v%20680.28%20H%203318.13%20v%20-286%20l%20-475.37,843.12%20H%201966.17%20L%201489.36,3391.7%20v%20288.54%20H%200%20v%20-680.28%20h%20300%20c%200,0%20-0.211,-830.21%20-0.496,-1326.22%20H%2014.3516%20V%201002.55%20H%20313.242%20C%20342.711,816.082%20426.352,613.191%20655.16,444.609%201017.33,177.738%201453.3,0%202403.75,0%20c%20950.44,0.0117188%201386.41,177.738%201748.58,444.609%20191.4,141%20279.76,370.411%20320.62,557.941%20h%20321.62%20v%20671.19%20h%20-286.64%20v%201326.22%20h%20299.56'%20/%3e%3cpath%20id='path16'%20style='fill:%230c2950;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='M%203508.27,853.781%20C%203262.82,717.398%203031.02,629.809%202403.75,629.809%20c%20-627.28,0%20-859.08,87.589%20-1104.53,223.972%20-85.31,47.367%20-144.91,97%20-186.97,148.769%20H%20451.078%20C%20479.703,848.16%20553.043,688.25%20735.582,553.75%201081.03,299.238%201485.58,135.609%202403.75,135.609%20c%20918.16,0%201322.71,163.629%201668.14,418.141%20182.54,134.5%20255.9,294.41%20284.52,448.8%20H%203695.24%20C%203653.18,950.781%203593.57,901.148%203508.27,853.781'%20/%3e%3cpath%20id='path18'%20style='fill:%230c2950;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='m%203790.1,3153.73%20c%200,-60.62%200,-305%200,-596.54%20l%20498.1,-883.45%20h%2083.68%20c%200,513.27%200,1461.81%200,1461.81%20h%20300%20v%20409.08%20H%203453.74%20v%20-390.9%20h%20336.36'%20/%3e%3cpath%20id='path20'%20style='fill:%230c2950;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='m%201017.4,2554.65%20c%200,292.67%200,538.28%200,599.08%20h%20336.36%20v%20390.9%20H%20135.602%20v%20-409.08%20h%20300%20c%200,0%200,-948.54%200,-1461.81%20h%2085.14%20l%20496.658,880.91'%20/%3e%3cpath%20id='path22'%20style='fill:%230c2950;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='m%201890.84,2547.25%20h%201063.63%20l%20-527.99,928.71%20-535.64,-928.71%20m%20872.7,1554.51%201445.45,-2563.6%20h%20449.99%20v%20-400%20H%202981.74%20v%20400%20h%20537.19%20l%20-327.25,590.92%20H%201664.43%20L%201337.16,1547.24%20H%201827.2%20V%201138.16%20H%20149.973%20v%20400%20h%20449.968%20l%201445.449,2563.6%20h%20718.15'%20/%3e%3cpath%20id='path24'%20style='fill:%230c2950;fill-opacity:1;fill-rule:nonzero;stroke:none'%20d='m%204483.28,525.449%20v%2041.461%20h%2027.54%20c%2014.08,0%2029.08,-3.109%2029.08,-19.66%200,-20.57%20-15.3,-21.801%20-32.43,-21.801%20h%20-24.19%20m%200,-17.14%20h%2023.25%20l%2035.21,-57.649%20h%2022.63%20l%20-37.95,58.59%20c%2019.6,2.43%2034.6,12.828%2034.6,36.77%200,26.39%20-15.61,38%20-47.14,38%20h%20-50.84%20V%20450.66%20h%2020.24%20z%20m%2024.48,-106.368%20c%2063.02,0%20116.61,48.719%20116.61,115.571%200,66.508%20-53.59,115.136%20-116.61,115.136%20-63.8,0%20-117.69,-48.628%20-117.69,-115.136%200,-66.852%2053.89,-115.571%20117.69,-115.571%20z%20m%20-94.57,115.571%20c%200,54.898%2041.54,95.976%2094.57,95.976%2052.32,0%2093.48,-41.078%2093.48,-95.976%200,-55.543%20-41.16,-96.442%20-93.48,-96.442%20-53.03,0%20-94.57,40.899%20-94.57,96.442'%20/%3e%3c/g%3e%3c/g%3e%3c/svg%3e",
}

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
    # Handle data URLs (e.g., inline SVG) directly without HTTP fetch.
    if url.startswith("data:"):
        mime = url.split(";", 1)[0].split(":")[1] if ";" in url else url.split(":", 1)[1]
        ext = ".svg" if "svg" in mime else ".png"
        payload = url.split(",", 1)[1] if "," in url else ""
        try:
            if ";base64" in url:
                content = base64.b64decode(payload)
            else:
                content = unquote(payload).encode("utf-8")
        except Exception as e:
            print(f"  ERROR decoding data URL for {team_name}: {e}")
            return ""

        filename = slugify(team_name) + ext
        filepath = os.path.join(LOGO_DIR, filename)
        try:
            with open(filepath, "wb") as f:
                f.write(content)
            return filepath
        except Exception as e:
            print(f"  ERROR writing data URL logo for {team_name}: {e}")
            return ""

    ext = guess_extension(url)

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
        "main-header__logo-scroll", # Abilene Christian variant
        "main-logo",                # Bryant
        "main-logo-1",              # Campbell variant
        "primary",                  # Belmont Sidearm header mark
        "header__logo-image",       # Auburn variant
    ]
    for cls in class_patterns:
        img_match = re.search(fr'<img[^>]+class="[^">]*{re.escape(cls)}[^">]*"[^>]*>', html, re.IGNORECASE)
        if not img_match:
            continue
        tag = img_match.group(0)
        url = select_best_img_url(tag)
        if url:
            return url
    # Belmont: logo wrapped in a div.main_header__logo with img.primary
    container = re.search(r'<div[^>]+class="[^">]*main_header__logo[^">]*"[^>]*>(.*?)</div>', html, re.IGNORECASE | re.DOTALL)
    if container:
        inner = container.group(1)
        img_match = re.search(r'<img[^>]+class="[^">]*primary[^">]*"[^>]*>', inner, re.IGNORECASE)
        if img_match:
            tag = img_match.group(0)
            url = select_best_img_url(tag)
            if url:
                return url
    return ""


def clean_image_url(url: str) -> str:
    """Decode HTML entities, unwrap Sidearm convert URLs, and normalize protocol-relative URLs."""
    if not url:
        return ""
    url = html.unescape(url).strip()
    # Strip common CSS wrappers like url(...) and trailing ); or quotes
    if url.startswith("url(") and url.endswith(")"):
        url = url[4:-1].strip(" '\"")
    url = url.strip(" '\"")
    if url.endswith(");"):
        url = url[:-2]
        url = url.strip(" '\"")
    parts = urlsplit(url)
    # Unwrap Sidearm image proxy links to get the original asset (often SVG/PNG)
    if "images.sidearmdev.com" in parts.netloc and parts.path.startswith("/convert"):
        qs = parse_qs(parts.query)
        inner = qs.get("url", [])
        if inner:
            url = unquote(inner[0])
            parts = urlsplit(url)
    if url.startswith("//"):
        url = "https:" + url
    return url


def select_best_img_url(tag: str) -> str:
    """
    From an <img> tag string, collect possible URLs (src, data-src, srcset) and
    prefer SVGs if present, otherwise return the first found.
    """
    candidates: list[str] = []
    for attr in ("src", "data-src"):
        m = re.search(fr'{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if m:
            candidates.append(m.group(1).strip())
    for attr in ("srcset", "data-srcset"):
        m = re.search(fr'{attr}=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if m:
            entries = [e.strip().split()[0] for e in m.group(1).split(",") if e.strip()]
            candidates.extend(entries)

    if not candidates:
        return ""

    for c in candidates:
        if ".svg" in c.lower():
            return c
    return candidates[0]


def find_svg_logo(html: str) -> str:
    """
    Scan the page for any SVG URLs containing 'logo' or 'nav_logo'.
    Useful when the logo is not referenced via predictable classes.
    """
    matches = re.findall(r'https?://[^\s"\\\']+\.svg[^\s"\\\']*', html, re.IGNORECASE)
    preferred = [m for m in matches if "logo" in m.lower()]
    if preferred:
        return preferred[0]
    return matches[0] if matches else ""


def guess_extension(url: str) -> str:
    """
    Choose a sensible file extension from URL path or query parameters.
    Handles Sidearm-style ?type=jpeg and strips query fragments from the ext.
    """
    if url.startswith("data:"):
        if "svg" in url[:50]:
            return ".svg"
        if "jpeg" in url[:50]:
            return ".jpeg"
        if "jpg" in url[:50]:
            return ".jpg"
        return ".png"
    if not url:
        return ".png"
    parts = urlsplit(url)
    ext = os.path.splitext(parts.path)[1]
    if ext and "&" in ext:
        ext = ext.split("&", 1)[0]
    if not ext:
        qs = parse_qs(parts.query)
        type_vals = qs.get("type", [])
        if any(v.lower().endswith("jpeg") or v.lower() == "jpeg" for v in type_vals):
            ext = ".jpeg"
        elif any("jpg" in v.lower() for v in type_vals):
            ext = ".jpg"
    if not ext:
        ext = ".png"
    return ext


def fetch_team_site_logo_url(team_name: str) -> str:
    """
    Fallback: fetch roster page and grab og:image/twitter:image as a logo candidate.
    """
    # Manual override for specific teams
    override = TEAM_LOGO_OVERRIDES.get(normalize_school_key(team_name))
    if override:
        return override

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
    # Try meta tags first
    logo_url = clean_image_url(extract_og_image(html))

    # Prefer direct header logo (often SVG) over proxied convert URLs or missing og:image
    header_logo = clean_image_url(extract_header_logo(html))
    if header_logo and (not logo_url or not logo_url.lower().endswith(".svg")):
        logo_url = header_logo

    # As a last resort, scan for any SVG with "logo" in the URL
    if (not logo_url) or not logo_url.lower().endswith(".svg"):
        svg_logo = clean_image_url(find_svg_logo(html))
        if svg_logo:
            logo_url = svg_logo

    if not logo_url:
        print("  No og:image/twitter:image or header logo found on roster page.")
        return ""

    return logo_url


# ---------------- MAIN ----------------

def main(selected_teams: list[str] | None = None):
    # Use configured team list instead of scraping Wikipedia so we skip Commons entirely.
    schools = sorted({t["team"] for t in TEAMS})
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

        # Directly fetch team-site logo (no Wikipedia/Commons lookup).
        best = None
        source = "team_site"

        fallback_url = fetch_team_site_logo_url(school)
        if fallback_url:
            best = {
                "title": "Team site logo",
                "url": fallback_url,
                "mime": "",
                "score": 0
            }
            print("  ✔ Found logo from team site.")
        else:
            print("  ❌ No logo found on team site.")

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
