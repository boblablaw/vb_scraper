# settings/__init__.py
"""Configuration package placeholder; loaders moved to scripts/.*"""

# Keep imports working for existing callers by redirecting to scripts loaders
from scripts.teams_loader import load_teams
from scripts.transfers_loader import load_transfers
from scripts.rpi_aliases_loader import load_rpi_aliases
from scripts.incoming_players_data import RAW_INCOMING_TEXT, get_raw_incoming_text

TEAMS = load_teams()
OUTGOING_TRANSFERS = load_transfers()
RPI_TEAM_NAME_ALIASES = load_rpi_aliases()

__all__ = ["TEAMS", "OUTGOING_TRANSFERS", "RPI_TEAM_NAME_ALIASES", "RAW_INCOMING_TEXT"]
