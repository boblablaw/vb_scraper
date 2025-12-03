# team_analysis.py
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from settings import RPI_TEAM_NAME_ALIASES
import requests
import re
from .utils import (
    fetch_html,
    normalize_player_name,
    normalize_class,
    normalize_height,
    normalize_school_key,
    extract_position_codes,
    canonical_name,
)
from .roster import parse_roster
from .stats import build_stats_lookup, attach_stats_to_player
from .logging_utils import get_logger

logger = get_logger(__name__)


def strip_year_from_url(url: str) -> str:
    """
    Remove trailing /<year> segment from a URL path, preserving query string.
    Handles patterns like /roster/2025 or /roster/2025/?view=table.
    """
    if not url:
        return url
    parts = urlsplit(url)
    segments = parts.path.rstrip("/").split("/")
    if segments and re.fullmatch(r"\d{4}", segments[-1]):
        segments = segments[:-1]
        new_path = "/".join(s for s in segments if s)
        if parts.path.startswith("/"):
            new_path = "/" + new_path
        return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))
    return url

def analyze_team(team_info: Dict[str, Any], rpi_lookup: Dict[str, Dict[str, str]] | None = None) -> List[Dict[str, Any]]:
    team_name = team_info["team"]
    conference = team_info.get("conference", "")
    roster_url = team_info["url"]
    stats_url = team_info.get("stats_url", "")

    logger.info("Analyzing team: %s", team_name)

    original_roster_url = roster_url
    fallback_used = False

    # Roster HTML (with fallback if year-appended URL 404s)
    try:
        roster_html = fetch_html(roster_url)
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            # If URL ends with a year segment, try stripping it
            fallback_url = strip_year_from_url(roster_url)
            if fallback_url != roster_url:
                logger.warning(
                    "Roster 404 for %s, retrying without year: %s -> %s",
                    team_name,
                    roster_url,
                    fallback_url,
                )
                try:
                    roster_html = fetch_html(fallback_url)
                    roster_url = fallback_url  # keep for logging/debug
                    fallback_used = True
                except Exception as e2:
                    logger.error(
                        "Fallback roster fetch failed for %s (%s): %s",
                        team_name,
                        fallback_url,
                        e2,
                    )
                    return []
            else:
                logger.error("ERROR fetching roster for %s: %s", team_name, e)
                return []
        else:
            logger.error("ERROR fetching roster for %s: %s", team_name, e)
            return []
    except Exception as e:
        logger.error("ERROR fetching roster for %s: %s", team_name, e)
        return []

    players = parse_roster(roster_html, roster_url)

    # If nothing parsed and URL had a year suffix, try once more without it
    if not players and not fallback_used:
        fallback_url = strip_year_from_url(original_roster_url)
        if fallback_url != original_roster_url:
            logger.warning(
                "No players parsed for %s; retrying without year: %s -> %s",
                team_name,
                original_roster_url,
                fallback_url,
            )
            try:
                roster_html = fetch_html(fallback_url)
                players = parse_roster(roster_html, fallback_url)
            except Exception as e:
                logger.error(
                    "Fallback roster parse failed for %s (%s): %s",
                    team_name,
                    fallback_url,
                    e,
                )
                return []

    # If too few players parsed (likely wrong year), try without year once
    if players and len(players) < 6 and not fallback_used:
        fallback_url = strip_year_from_url(original_roster_url)
        if fallback_url != original_roster_url:
            logger.warning(
                "Only %d players parsed for %s; retrying without year: %s -> %s",
                len(players),
                team_name,
                original_roster_url,
                fallback_url,
            )
            try:
                roster_html = fetch_html(fallback_url)
                retry_players = parse_roster(roster_html, fallback_url)
                if retry_players:
                    players = retry_players
            except Exception as e:
                logger.error(
                    "Retry without year failed for %s (%s): %s",
                    team_name,
                    fallback_url,
                    e,
                )

    if not players:
        logger.warning("No players parsed for team %s from %s", team_name, roster_url)
        return []

    blocklist = {
        "university of texas": {"torrey stafford"},
        "coppin state university": {"takenya stafford"},
        "temple university": {"lainey team impact"},
        "georgia institute of technology": {"luanna emiliano", "bruno dewes", "leo weng"},
        "university of california, davis": {"maren b."},
        "western kentucky university": {"harlie bryant"},
    }
    team_key = team_name.lower().strip()
    if team_key in blocklist:
        filtered_players = []
        for p in players:
            nm = canonical_name(p.get("name", ""))
            if nm in blocklist[team_key]:
                logger.info("Dropping blocked player %s for team %s", p.get("name", ""), team_name)
                continue
            filtered_players.append(p)
        players = filtered_players

    def _dedupe_repeated_name(name: str) -> str:
        """
        Some sources emit a name twice in the same string (e.g., 'Annabelle Denommé Annabelle Denommé').
        If the first half of the tokens equals the second half, keep only one instance.
        """
        parts = name.split()
        if len(parts) % 2 == 0:
            half = len(parts) // 2
            if parts[:half] == parts[half:]:
                return " ".join(parts[:half])
        return name

    # Per-player normalization
    for p in players:
        raw_name = p.get("name", "")
        clean_name = normalize_player_name(raw_name)
        clean_name = _dedupe_repeated_name(clean_name)
        p["name"] = clean_name

        class_raw = p.get("class_raw", "")
        class_norm = normalize_class(class_raw)
        p["class_norm"] = class_norm

        position_raw = p.get("position", "")
        p["position_raw"] = position_raw
        # Extract normalized position codes (S, OH, RS, MB, DS)
        position_codes = extract_position_codes(position_raw)
        p["position_norm"] = "/".join(sorted(position_codes)) if position_codes else ""

        height_raw = p.get("height_raw", "")
        height_norm = normalize_height(height_raw)
        p["height_norm"] = height_norm

    if not players:
        logger.warning("No players for team %s", team_name)
        return []

    stats_lookup = {}
    if stats_url:
        try:
            stats_lookup = build_stats_lookup(stats_url)
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            if status == 404:
                fallback_stats_url = strip_year_from_url(stats_url)
                if fallback_stats_url != stats_url:
                    logger.warning(
                        "Stats 404 for %s, retrying without year: %s -> %s",
                        team_name,
                        stats_url,
                        fallback_stats_url,
                    )
                    try:
                        stats_lookup = build_stats_lookup(fallback_stats_url)
                        stats_url = fallback_stats_url
                    except Exception as e2:
                        logger.error(
                            "Fallback stats fetch failed for %s (%s): %s",
                            team_name,
                            fallback_stats_url,
                            e2,
                        )
                        stats_lookup = {}
                else:
                    logger.error("ERROR fetching stats for %s: %s", team_name, e)
            else:
                logger.error("ERROR fetching stats for %s: %s", team_name, e)
        except Exception as e:
            logger.error("ERROR fetching stats for %s: %s", team_name, e)
            stats_lookup = {}

    rows: List[Dict[str, Any]] = []

    for p in players:
        position_raw = p.get("position_raw", p.get("position", ""))
        position_norm = p.get("position_norm", "")

        class_raw = p.get("class_raw", "")
        class_norm = p.get("class_norm", normalize_class(class_raw))

        height_raw = p.get("height_raw", "")
        height_norm = p.get("height_norm", normalize_height(height_raw))

        base: Dict[str, Any] = {
            "team": team_name,
            "conference": conference,
            "name": p["name"],
            "position": position_norm,
            "class": class_norm,
            "height": height_norm,
        }

        base = attach_stats_to_player(base, stats_lookup)
        rows.append(base)

    return rows
