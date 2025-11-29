# team_analysis.py
from __future__ import annotations

from typing import Any, Dict, List

from settings import RPI_TEAM_NAME_ALIASES
from utils import (
    fetch_html,
    normalize_player_name,
    normalize_class,
    normalize_height,
    excel_protect_record,
    normalize_school_key,
    extract_position_codes,
    is_graduating,
    class_next_year,
)
from roster import parse_roster
from coaches import find_coaches_page_url, parse_coaches_from_html, pack_coaches_for_row
from transfers import (
    is_outgoing_transfer,
    is_incoming_transfer,
    get_incoming_setters_for_team,
    get_incoming_pin_hitters_for_team,
    get_incoming_middles_for_team,
    get_incoming_def_specialists_for_team,
)
from labels import format_incoming_player_label, format_returning_player_label
from stats import build_stats_lookup, attach_stats_to_player
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
    rpi_record_raw = rpi_data.get("rpi_record", "")
    rpi_record = excel_protect_record(rpi_record_raw)

    # Coaches: try dedicated coaches page first
    coaches_html = roster_html
    alt_coaches_url = find_coaches_page_url(roster_html, roster_url)
    if alt_coaches_url:
        try:
            coaches_html = fetch_html(alt_coaches_url)
        except Exception as e:
            logger.warning("Could not fetch coaches page %s: %s", alt_coaches_url, e)
    coaches = parse_coaches_from_html(coaches_html)
    coach_cols = pack_coaches_for_row(coaches)

    # Per-player normalization / flags
    for p in players:
        raw_name = p.get("name", "")
        clean_name = normalize_player_name(raw_name)
        p["name"] = clean_name

        class_raw = p.get("class_raw", "")
        class_norm = normalize_class(class_raw)
        p["class_norm"] = class_norm

        position_raw = p.get("position", "")
        codes = extract_position_codes(position_raw)
        position_norm = "/".join(sorted(codes)) if codes else ""
        p["position_raw"] = position_raw
        p["position_norm"] = position_norm

        height_raw = p.get("height_raw", "")
        height_norm = normalize_height(height_raw)
        p["height_norm"] = height_norm

        # Do NOT count S/DS as a setter
        is_setter_flag = ("S" in codes) and ("DS" not in codes)
        is_pin_flag = ("OH" in codes) or ("RS" in codes)
        is_mb_flag = "MB" in codes
        is_def_flag = "DS" in codes

        p["is_setter_flag"] = is_setter_flag
        p["is_pin_flag"] = is_pin_flag
        p["is_mb_flag"] = is_mb_flag
        p["is_def_flag"] = is_def_flag

        is_grad_flag = is_graduating(class_norm)
        is_xfer_out = is_outgoing_transfer(clean_name, team_name)
        is_xfer_in = is_incoming_transfer(clean_name, team_name)

        p["is_grad_flag"] = is_grad_flag
        p["is_xfer_out"] = is_xfer_out
        p["is_xfer_in"] = is_xfer_in

    returning_players = [
        p for p in players
        if not p["is_grad_flag"] and not p["is_xfer_out"]
    ]
    returning_setters_2026 = [p for p in returning_players if p["is_setter_flag"]]
    returning_pins_2026 = [p for p in returning_players if p["is_pin_flag"]]
    returning_mbs_2026 = [p for p in returning_players if p["is_mb_flag"]]
    returning_defs_2026 = [p for p in returning_players if p["is_def_flag"]]

    returning_setter_count_2026 = len(returning_setters_2026)
    returning_pin_count_2026 = len(returning_pins_2026)
    returning_mb_count_2026 = len(returning_mbs_2026)
    returning_def_count_2026 = len(returning_defs_2026)

    returning_setter_names_2026 = (
        ", ".join(format_returning_player_label(p) for p in returning_setters_2026)
        if returning_setters_2026 else ""
    )
    returning_pin_names_2026 = (
        ", ".join(format_returning_player_label(p) for p in returning_pins_2026)
        if returning_pins_2026 else ""
    )
    returning_mb_names_2026 = (
        ", ".join(format_returning_player_label(p) for p in returning_mbs_2026)
        if returning_mbs_2026 else ""
    )
    returning_def_names_2026 = (
        ", ".join(format_returning_player_label(p) for p in returning_defs_2026)
        if returning_defs_2026 else ""
    )

    incoming_setters = get_incoming_setters_for_team(team_name)
    incoming_pin_hitters = get_incoming_pin_hitters_for_team(team_name)
    incoming_middles = get_incoming_middles_for_team(team_name)
    incoming_defs = get_incoming_def_specialists_for_team(team_name)

    incoming_setter_count_2026 = len(incoming_setters)
    incoming_pin_count_2026 = len(incoming_pin_hitters)
    incoming_mb_count_2026 = len(incoming_middles)
    incoming_def_count_2026 = len(incoming_defs)

    incoming_setter_names_2026 = (
        ", ".join(format_incoming_player_label(p) for p in incoming_setters)
        if incoming_setters else ""
    )
    incoming_pin_names_2026 = (
        ", ".join(format_incoming_player_label(p) for p in incoming_pin_hitters)
        if incoming_pin_hitters else ""
    )
    incoming_mb_names_2026 = (
        ", ".join(format_incoming_player_label(p) for p in incoming_middles)
        if incoming_middles else ""
    )
    incoming_def_names_2026 = (
        ", ".join(format_incoming_player_label(p) for p in incoming_defs)
        if incoming_defs else ""
    )

    projected_setter_count_2026 = returning_setter_count_2026 + incoming_setter_count_2026
    projected_pin_count_2026 = returning_pin_count_2026 + incoming_pin_count_2026
    projected_mb_count_2026 = returning_mb_count_2026 + incoming_mb_count_2026
    projected_def_count_2026 = returning_def_count_2026 + incoming_def_count_2026

    total_pure_setters = sum(1 for p in players if p["is_setter_flag"])
    logger.info(
        "%s: pure setters = %d, returning_setters_2026 = %d, "
        "incoming_setters_2026 = %d, projected_setters_2026 = %d",
        team_name,
        total_pure_setters,
        returning_setter_count_2026,
        incoming_setter_count_2026,
        projected_setter_count_2026,
    )

    stats_lookup = build_stats_lookup(stats_url)

    rows: List[Dict[str, Any]] = []

    for p in players:
        position_raw = p.get("position_raw", p.get("position", ""))
        position_norm = p.get("position_norm", "")

        class_raw = p.get("class_raw", "")
        class_norm = p.get("class_norm", normalize_class(class_raw))
        class_next = class_next_year(class_norm) if class_norm else ""

        height_raw = p.get("height_raw", "")
        height_norm = p.get("height_norm", normalize_height(height_raw))
        height_safe = excel_protect_record(height_norm)

        base: Dict[str, Any] = {
            "team": team_name,
            "conference": conference,
            "roster_url": roster_url,
            "stats_url": stats_url,
            "team_rpi_rank": rpi_rank,
            "team_overall_record": rpi_record,

            "name": p["name"],
            "position_raw": position_raw,
            "position": position_norm,

            "class_raw": class_raw,
            "class": class_norm,
            "class_next_year": class_next,

            "height_raw": height_raw,
            "height": height_safe,

            "is_setter": int(p["is_setter_flag"]),
            "is_pin_hitter": int(p["is_pin_flag"]),
            "is_middle_blocker": int(p["is_mb_flag"]),
            "is_def_specialist": int(p["is_def_flag"]),
            "is_graduating": int(p["is_grad_flag"]),
            "is_outgoing_transfer": int(p["is_xfer_out"]),
            "is_incoming_transfer": int(p["is_xfer_in"]),

            # 2026 SETTERS
            "returning_setter_count_2026": returning_setter_count_2026,
            "returning_setter_names_2026": returning_setter_names_2026,
            "incoming_setter_count_2026": incoming_setter_count_2026,
            "incoming_setter_names_2026": incoming_setter_names_2026,
            "projected_setter_count_2026": projected_setter_count_2026,

            # 2026 PINS
            "returning_pin_hitter_count_2026": returning_pin_count_2026,
            "returning_pin_hitter_names_2026": returning_pin_names_2026,
            "incoming_pin_hitter_count_2026": incoming_pin_count_2026,
            "incoming_pin_hitter_names_2026": incoming_pin_names_2026,
            "projected_pin_hitter_count_2026": projected_pin_count_2026,

            # 2026 MIDS
            "returning_middle_blocker_count_2026": returning_mb_count_2026,
            "returning_middle_blocker_names_2026": returning_mb_names_2026,
            "incoming_middle_blocker_count_2026": incoming_mb_count_2026,
            "incoming_middle_blocker_names_2026": incoming_mb_names_2026,
            "projected_middle_blocker_count_2026": projected_mb_count_2026,

            # 2026 DS/L
            "returning_def_specialist_count_2026": returning_def_count_2026,
            "returning_def_specialist_names_2026": returning_def_names_2026,
            "incoming_def_specialist_count_2026": incoming_def_count_2026,
            "incoming_def_specialist_names_2026": incoming_def_names_2026,
            "projected_def_specialist_count_2026": projected_def_count_2026,
        }

        base.update(coach_cols)
        base = attach_stats_to_player(base, stats_lookup)
        rows.append(base)

    return rows