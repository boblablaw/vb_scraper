#!/usr/bin/env python3
"""Find volleyball stats PDFs for teams missing Sidearm S3 PDFs.

This script looks at the coverage CSV produced by download_sidearm_pdfs.py and,
for teams where has_pdf == False, attempts to find alternative volleyball stats
PDFs by scanning each team's stats_url page for links to .pdf files that look
like volleyball stats.

Heuristics:
- Fetch the team's stats_url (with year appended via settings.teams_urls)
- Parse all <a> tags with href ending in .pdf
- Prefer links whose URL or link text contains volleyball-related keywords
  (e.g., 'vb', 'wvball', 'volleyball', 'stats', 'cume', 'season')
- Download the best-matching PDF (if any) into exports/vb_stats_pdfs
- Write a CSV report listing which teams we found PDFs for
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings.teams_urls import get_teams_with_year_urls, get_season_year


DEFAULT_COVERAGE_CSV = "exports/sidearm_pdfs/sidearm_pdfs_coverage_{year}.csv"
DEFAULT_OUTPUT_DIR = "exports/vb_stats_pdfs"


def load_missing_teams(coverage_csv: str) -> set[str]:
    """Load set of team names where has_pdf is False from coverage CSV."""
    missing = set()
    if not os.path.exists(coverage_csv):
        raise FileNotFoundError(f"Coverage CSV not found: {coverage_csv}")

    with open(coverage_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            has_pdf_raw = (row.get("has_pdf") or "").strip().lower()
            has_pdf = has_pdf_raw in ("true", "1", "yes", "y")
            if not has_pdf:
                team = (row.get("team") or "").strip()
                if team:
                    missing.add(team)
    return missing


KEYWORDS_PRIMARY = ["vb", "wvball", "wvolley", "volleyball", "wvb"]
KEYWORDS_STATS = ["stats", "stat", "cume", "season", "cumulative"]


def score_pdf_link(href: str, text: str) -> int:
    """Score a candidate PDF link based on URL and link text."""
    href_l = href.lower()
    text_l = (text or "").lower()
    score = 0

    # Prefer obvious volleyball references
    if any(k in href_l or k in text_l for k in KEYWORDS_PRIMARY):
        score += 5

    # Prefer stats-related references
    if any(k in href_l or k in text_l for k in KEYWORDS_STATS):
        score += 3

    # Slight preference if under a documents or stats path
    if "/documents/" in href_l or "/stats" in href_l:
        score += 2

    return score


def find_best_pdf_url(page_url: str, html: str) -> Optional[str]:
    """Find the best candidate stats PDF URL on a stats page.

    Returns an absolute URL or None if nothing suitable is found.
    """
    soup = BeautifulSoup(html, "html.parser")

    candidates: list[tuple[int, str]] = []  # (score, absolute_url)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" not in href.lower():
            continue

        abs_url = urljoin(page_url, href)
        # Basic sanity: ensure it's HTTP(S)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue

        score = score_pdf_link(abs_url, a.get_text(strip=True) or "")
        if score <= 0:
            # Still keep unscored links as very low priority
            score = 1
        candidates.append((score, abs_url))

    if not candidates:
        return None

    # Choose the highest-scoring candidate
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def normalize_team_for_filename(team: str) -> str:
    """Normalize team name into a filesystem-friendly slug."""
    slug = team.lower()
    for ch in [" ", "/", "\\", "'", ",", ".", "(", ")", "&"]:
        slug = slug.replace(ch, "_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "team"


def discover_and_download_pdfs(year: int,
                               coverage_csv: str,
                               output_dir: str,
                               timeout: int = 10) -> str:
    """Discover and download volleyball stats PDFs for missing teams.

    Returns the path to a CSV report summarizing findings.
    """
    os.makedirs(output_dir, exist_ok=True)

    missing_teams = load_missing_teams(coverage_csv)
    print(f"Loaded {len(missing_teams)} missing team(s) from {coverage_csv}")

    teams_with_year = get_teams_with_year_urls(year)
    teams_by_name = {t["team"]: t for t in teams_with_year}

    session = requests.Session()
    session.headers.update({"User-Agent": "vb_scraper/1.0 (+https://example.com)"})

    report_rows: list[dict] = []

    for team_name in sorted(missing_teams):
        team_info = teams_by_name.get(team_name)
        if not team_info:
            print(f"[WARN] Team from coverage CSV not in TEAMS list: {team_name}")
            continue

        stats_url = team_info.get("stats_url") or team_info.get("url")
        if not stats_url:
            print(f"[SKIP] {team_name}: no stats_url/url defined")
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": "",
                    "found_pdf_url": "",
                    "local_filename": "",
                    "status": "no_stats_url",
                }
            )
            continue

        print(f"[SCAN] {team_name}: {stats_url}")

        try:
            resp = session.get(stats_url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] request failed: {exc}")
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": stats_url,
                    "found_pdf_url": "",
                    "local_filename": "",
                    "status": f"request_error:{exc}",
                }
            )
            continue

        if resp.status_code != 200:
            print(f"  [ERROR] HTTP {resp.status_code} fetching stats page")
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": stats_url,
                    "found_pdf_url": "",
                    "local_filename": "",
                    "status": f"http_{resp.status_code}",
                }
            )
            continue

        pdf_url = find_best_pdf_url(stats_url, resp.text)
        if not pdf_url:
            print("  [MISS] No suitable PDF links found on stats page")
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": stats_url,
                    "found_pdf_url": "",
                    "local_filename": "",
                    "status": "no_pdf_links",
                }
            )
            continue

        print(f"  [CANDIDATE] {pdf_url}")

        # Try downloading the candidate PDF
        try:
            pdf_resp = session.get(pdf_url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] PDF request failed: {exc}")
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": stats_url,
                    "found_pdf_url": pdf_url,
                    "local_filename": "",
                    "status": f"pdf_request_error:{exc}",
                }
            )
            continue

        if pdf_resp.status_code != 200 or "application/pdf" not in (
            pdf_resp.headers.get("Content-Type", "").lower()
        ):
            print(
                "  [MISS] Candidate PDF URL did not return a PDF "
                f"(status={pdf_resp.status_code}, content-type={pdf_resp.headers.get('Content-Type')})"
            )
            report_rows.append(
                {
                    "team": team_name,
                    "conference": team_info.get("conference", ""),
                    "stats_url": stats_url,
                    "found_pdf_url": pdf_url,
                    "local_filename": "",
                    "status": "candidate_not_pdf",
                }
            )
            continue

        team_slug = normalize_team_for_filename(team_name)
        local_filename = f"{team_slug}_vb_stats_{year}.pdf"
        local_path = os.path.join(output_dir, local_filename)

        with open(local_path, "wb") as f:
            f.write(pdf_resp.content)

        print(f"  [OK] Saved PDF to {local_path}")

        report_rows.append(
            {
                "team": team_name,
                "conference": team_info.get("conference", ""),
                "stats_url": stats_url,
                "found_pdf_url": pdf_url,
                "local_filename": local_filename,
                "status": "ok",
            }
        )

    report_path = os.path.join(output_dir, f"vb_stats_pdfs_report_{year}.csv")
    fieldnames = [
        "team",
        "conference",
        "stats_url",
        "found_pdf_url",
        "local_filename",
        "status",
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"\nReport written to: {report_path}")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and download volleyball stats PDFs for teams missing "
            "Sidearm S3 PDFs, based on the coverage CSV."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help=(
            "Season year to use for stats URLs and filenames (e.g., 2025). "
            "If omitted, uses settings.teams_urls.get_season_year()."
        ),
    )
    parser.add_argument(
        "--coverage-csv",
        default=None,
        help=(
            "Path to the coverage CSV from download_sidearm_pdfs.py. "
            "Default: exports/sidearm_pdfs/sidearm_pdfs_coverage_{year}.csv."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save discovered PDFs and report (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)",
    )

    args = parser.parse_args()

    year = args.year or get_season_year()

    if args.coverage_csv:
        coverage_csv = args.coverage_csv
    else:
        coverage_csv = DEFAULT_COVERAGE_CSV.format(year=year)

    discover_and_download_pdfs(
        year=year,
        coverage_csv=coverage_csv,
        output_dir=args.output_dir,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
