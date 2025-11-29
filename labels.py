# labels.py
from __future__ import annotations

from typing import Any, Dict, List, Set

from utils import (
    normalize_text,
    extract_position_codes,
    normalize_class,
    class_next_year,
)


def format_player_label(name: str, pos_codes: Set[str], class_label: str) -> str:
    """
    Build a label like:
        'Molly Beatty (S - So)'
    """
    name = normalize_text(name)
    if not name:
        return ""

    pos_part = "/".join(sorted(pos_codes)) if pos_codes else ""
    class_part = normalize_class(class_label)

    bits: List[str] = []
    if pos_part:
        bits.append(pos_part)
    if class_part:
        bits.append(class_part)

    if bits:
        return f"{name} ({' - '.join(bits)})"
    return name


def format_incoming_player_label(p: Dict[str, Any]) -> str:
    """
    Use the INCOMING_PLAYERS dict to build 'Name (S - So)' style labels.
    """
    name = p.get("name", "")
    pos_codes = extract_position_codes(p.get("position", ""))

    class_raw = ""
    for key in ("class_next_year", "class_2026", "class", "year"):
        if p.get(key):
            class_raw = p[key]
            break

    return format_player_label(name, pos_codes, class_raw)


def format_returning_player_label(p: Dict[str, Any]) -> str:
    """
    Build labels for RETURNING roster players, using NEXT YEAR's class.
    """
    name = p.get("name", "")
    pos_source = p.get("position_raw", p.get("position", ""))
    pos_codes = extract_position_codes(pos_source)

    class_source = p.get("class_norm") or p.get("class_raw", "")
    class_next = class_next_year(class_source) if class_source else ""

    return format_player_label(name, pos_codes, class_next)
