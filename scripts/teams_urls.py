# Year-based URL helpers for roster/stat scraping.
# Appends season year to roster and stats URLs so the scraper points at the correct season.

from __future__ import annotations

from datetime import date
from typing import List, Dict
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from scripts.teams_loader import load_teams


def get_season_year(today: date | None = None) -> int:
    """
    Season rolls over on Aug 1.
    If month >= August, use current calendar year; otherwise use previous year.
    Example: Dec 2025 -> 2025 season; Feb 2025 -> 2024 season.
    """
    today = today or date.today()
    if today.month >= 8:
        return today.year
    return today.year - 1


def append_year_to_url(url: str, year: int) -> str:
    """
    Append or set year on a roster/stats URL.

    - If the URL has query parameters (e.g., teamstats.aspx?year=YYYY&...), set/replace
      the `year` parameter and return.
    - Otherwise, append `/YYYY` if not already present.
    """
    if not url:
        return url

    year_str = str(year)

    parts = urlsplit(url)
    if parts.query:
        qs = dict(parse_qsl(parts.query, keep_blank_values=True))
        qs["year"] = year_str
        new_query = urlencode(qs)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

    base = url.rstrip("/")
    # Prevent double-appending if URL already ends with the year
    if base.endswith(year_str):
        return url.rstrip("/") + "/"

    return f"{base}/{year_str}"


def get_teams_with_year_urls(year: int | None = None) -> List[Dict]:
    """
    Return TEAMS with roster and stats URLs updated to include the season year.
    """
    year = year or get_season_year()
    teams_with_year: List[Dict] = []

    teams = load_teams()
    for t in teams:
        team = dict(t)  # shallow copy
        # Allow per-team opt-out from year suffix
        if not t.get("roster_yearless"):
            team["url"] = append_year_to_url(t.get("url", ""), year)
        else:
            team["url"] = t.get("url", "")

        if t.get("stats_url"):
            if not t.get("stats_yearless"):
                team["stats_url"] = append_year_to_url(t["stats_url"], year)
            else:
                team["stats_url"] = t["stats_url"]
        teams_with_year.append(team)

    return teams_with_year


__all__ = ["get_season_year", "append_year_to_url", "get_teams_with_year_urls"]
