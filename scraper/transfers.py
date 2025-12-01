# transfers.py
from __future__ import annotations

from typing import Any, Dict, List

from .incoming_players import INCOMING_PLAYERS
from settings import OUTGOING_TRANSFERS

from .utils import normalize_text, normalize_school_key, extract_position_codes
from logging_utils import get_logger

logger = get_logger(__name__)


def is_transfer_for_team(player_name: str, team_name: str, direction: str) -> bool:
    """
    Generic helper:
      direction == "out" → match name + old_team
      direction == "in"  → match name + new_team
    """
    n = normalize_text(player_name).lower()
    team_key = normalize_school_key(team_name)

    for xfer in OUTGOING_TRANSFERS:
        xn = normalize_text(xfer.get("name", "")).lower()
        if n != xn:
            continue

        if direction == "out":
            src_key = normalize_school_key(xfer.get("old_team", ""))
            if src_key and src_key == team_key:
                return True

        elif direction == "in":
            dst_key = normalize_school_key(xfer.get("new_team", ""))
            if dst_key and dst_key == team_key:
                return True

    return False


def is_outgoing_transfer(player_name: str, team_name: str) -> bool:
    return is_transfer_for_team(player_name, team_name, "out")


def is_incoming_transfer(player_name: str, team_name: str) -> bool:
    return is_transfer_for_team(player_name, team_name, "in")


def incoming_for_team_by_code(team_name: str, target_code: str) -> List[Dict[str, Any]]:
    team_key = normalize_school_key(team_name)
    result: List[Dict[str, Any]] = []

    for p in INCOMING_PLAYERS:
        school = p.get("school", "")
        pos = p.get("position", "")
        school_key = normalize_school_key(school)
        if not school_key or school_key != team_key:
            continue

        codes = extract_position_codes(pos)
        if target_code == "S":
            if "S" in codes:
                result.append(p)
        elif target_code == "PIN":
            if "OH" in codes or "RS" in codes:
                result.append(p)
        elif target_code == "MB":
            if "MB" in codes:
                result.append(p)
        elif target_code == "DS":
            if "DS" in codes:
                result.append(p)

    logger.debug(
        "Found %d incoming %s players for team %s",
        len(result),
        target_code,
        team_name,
    )
    return result


def get_incoming_setters_for_team(team_name: str) -> List[Dict[str, Any]]:
    return incoming_for_team_by_code(team_name, "S")


def get_incoming_pin_hitters_for_team(team_name: str) -> List[Dict[str, Any]]:
    return incoming_for_team_by_code(team_name, "PIN")


def get_incoming_middles_for_team(team_name: str) -> List[Dict[str, Any]]:
    return incoming_for_team_by_code(team_name, "MB")


def get_incoming_def_specialists_for_team(team_name: str) -> List[Dict[str, Any]]:
    return incoming_for_team_by_code(team_name, "DS")
