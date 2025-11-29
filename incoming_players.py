import re
from typing import Dict, List


# =========================================================
# School aliases + normalizer (shared helper)
# =========================================================
# The *values* in this dict should match how the school appears
# (after normalization) in your d1_wvb_programs_base.csv file.
# =========================================================

SCHOOL_ALIASES: Dict[str, str] = {
    # --- Albany ---
    "university at albany": "ualbany",
    "ualbany": "ualbany",
    "albany": "ualbany",

    # --- Binghamton ---
    "binghamton university": "binghamton",
    "binghamton": "binghamton",

    # --- Bryant ---
    "bryant university": "bryant",
    "bryant": "bryant",

    # --- UMBC ---
    "university of maryland baltimore county": "umbc",
    "maryland baltimore county": "umbc",
    "umbc": "umbc",

    "the ohio state university": "ohio state university",

    # Add more as you discover mismatches:
    # "university of massachusetts lowell": "umass lowell",
    # "umass lowell": "umass lowell",
    # "stony brook university": "stony brook",
    # "university of new hampshire": "new hampshire",
    # "university of maine": "maine",
}


def normalize_school_key(name: str) -> str:
    """
    Normalize a school name into a lowercase, punctuation-stripped key,
    then apply alias mapping if defined.
    """
    if not name:
        return ""

    key = name.lower()
    key = re.sub(r"[^a-z0-9]+", " ", key)  # non-alnum -> space
    key = re.sub(r"\s+", " ", key).strip()  # collapse spaces

    return SCHOOL_ALIASES.get(key, key)


# =========================================================
# RAW INPUT BLOCK
#   - Now imported from settings/incoming_players_data.py
# =========================================================

from settings.incoming_players_data import RAW_INCOMING_TEXT


# =========================================================
# Parser for the raw input format
# =========================================================

def parse_raw_incoming_players(raw: str) -> List[Dict[str, str]]:
    """
    Parse the raw text block into a list of player dicts.

    Expected format:

        <Conference Name>:
        Player Name - School - Position (Club)
        Player Name - School - Position (Club)
        <Next Conference>:
        ...

    Club in parentheses is optional; position is optional but recommended.
    """
    players: List[Dict[str, str]] = []
    current_conf: str | None = None

    if not raw:
        return players

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Conference header line, e.g. "America East Conference:"
        if line.endswith(":"):
            current_conf = line.rstrip(":").strip()
            continue

        # Must have a current conference to attach players to
        if current_conf is None:
            # Skip lines before first conference header
            continue

        # Example line:
        # "Addy Bianchini - University at Albany - Setter/OPP (NKYVC)"

        # Extract club from parentheses at the end, if present
        club = ""
        club_match = re.search(r"\((.+)\)\s*$", line)
        if club_match:
            club = club_match.group(1).strip()
            # Remove the "(Club)" part from the working line
            line = line[:club_match.start()].rstrip()

        # Split the remaining part by " - "
        parts = [p.strip() for p in line.split(" - ")]
        # Minimum: name, school
        if len(parts) < 2:
            # malformed line, skip
            continue

        name = parts[0]
        school = parts[1]
        position = parts[2] if len(parts) >= 3 else ""

        players.append({
            "conference": current_conf,
            "school": school,
            "name": name,
            "position": position,
            "club": club,
        })

    return players


# =========================================================
# Optional: manual additions or overrides
#   - If you want to append extra players that don't come
#     from RAW_INCOMING_TEXT, put them here.
# =========================================================

MANUAL_EXTRA_PLAYERS: List[Dict[str, str]] = [
    # Example:
    # {
    #     "conference": "America East Conference",
    #     "school": "Some School",
    #     "name": "Some Player",
    #     "position": "MB",
    #     "club": "Some Club",
    # },
]


# =========================================================
# Final incoming players list
# =========================================================

INCOMING_PLAYERS: List[Dict[str, str]] = (
    parse_raw_incoming_players(RAW_INCOMING_TEXT) + MANUAL_EXTRA_PLAYERS
)


def get_incoming_players() -> List[Dict[str, str]]:
    """
    Convenience function so other scripts can import from here.
    """
    return INCOMING_PLAYERS
