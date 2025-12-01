# team_analysis.py
from __future__ import annotations

from typing import Any, Dict, List

from settings import RPI_TEAM_NAME_ALIASES
from .utils import (
    fetch_html,
    normalize_player_name,
    normalize_class,
    normalize_height,
    normalize_school_key,
)
from .roster import parse_roster
from .stats import build_stats_lookup, attach_stats_to_player
from logging_utils import get_logger

logger = get_logger(__name__)


def analyze_team(team_info: Dict[str, Any], rpi_lookup: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    team_name = team_info["team"]
    conference = team_info.get("conference", "")
    roster_url = team_info["url"]
    stats_url = team_info.get("stats_url", "")

    logger.info("Analyzing team: %s", team_name)

    # Roster HTML
    try:
        roster_html = fetch_html(roster_url)
    except Exception as e:
        logger.error("ERROR fetching roster for %s: %s", team_name, e)
        return []

    players = parse_roster(roster_html, roster_url)
    if not players:
        logger.warning("No players parsed for team %s from %s", team_name, roster_url)
        return []

#    for p in players:
#        logger.info(
#            "DEBUG ROSTER %s: name=%r pos=%r class_raw=%r height_raw=%r",
#            team_name,
#            p.get("name"),
#            p.get("position"),
#            p.get("class_raw"),
#            p.get("height_raw"),
#        )

    # RPI
    rpi_name = RPI_TEAM_NAME_ALIASES.get(team_name, team_name)
    rpi_key = normalize_school_key(rpi_name)
    rpi_data = rpi_lookup.get(rpi_key, {})
    rpi_rank = rpi_data.get("rpi_rank", "")
    rpi_record = rpi_data.get("rpi_record", "")

    # Per-player normalization
    for p in players:
        raw_name = p.get("name", "")
        clean_name = normalize_player_name(raw_name)
        p["name"] = clean_name

        class_raw = p.get("class_raw", "")
        class_norm = normalize_class(class_raw)
        p["class_norm"] = class_norm

        position_raw = p.get("position", "")
        p["position_raw"] = position_raw

        height_raw = p.get("height_raw", "")
        height_norm = normalize_height(height_raw)
        p["height_norm"] = height_norm

    if not players:
        logger.warning("No players for team %s", team_name)
        return []

    stats_lookup = build_stats_lookup(stats_url)

    rows: List[Dict[str, Any]] = []

    for p in players:
        position_raw = p.get("position_raw", p.get("position", ""))

        class_raw = p.get("class_raw", "")
        class_norm = p.get("class_norm", normalize_class(class_raw))

        height_raw = p.get("height_raw", "")
        height_norm = p.get("height_norm", normalize_height(height_raw))

        base: Dict[str, Any] = {
            "team": team_name,
            "conference": conference,
            "rank": rpi_rank,
            "record": rpi_record,

            "name": p["name"],
            "position": position_raw,

            "class": class_norm,

            "height": height_norm,
        }

        base = attach_stats_to_player(base, stats_lookup)
        rows.append(base)

    return rows
