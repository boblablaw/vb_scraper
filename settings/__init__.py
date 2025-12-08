# settings/__init__.py
"""Configuration package placeholder; loaders moved to scripts/.*"""

# Keep imports working for existing callers by redirecting to scripts loaders
from scripts.helpers.teams_loader import load_teams
from scripts.helpers.transfers_loader import load_transfers
from scripts.helpers.incoming_players_data import RAW_INCOMING_TEXT, get_raw_incoming_text

TEAMS = load_teams()
OUTGOING_TRANSFERS = load_transfers()


def _build_rpi_aliases():
    """
    Build a mapping of alias -> canonical team name using teams.json data.
    """
    aliases = {}
    for team in TEAMS:
        canonical = team.get("team") or ""
        if not canonical:
            continue

        candidates = [canonical]
        candidates.extend(team.get("team_name_aliases") or [])
        short_name = team.get("short_name")
        if short_name:
            candidates.append(short_name)

        for alias in candidates:
            alias_value = (alias or "").strip()
            if not alias_value:
                continue
            aliases[alias_value] = canonical

    return aliases


RPI_TEAM_NAME_ALIASES = _build_rpi_aliases()

__all__ = ["TEAMS", "OUTGOING_TRANSFERS", "RPI_TEAM_NAME_ALIASES", "RAW_INCOMING_TEXT"]
