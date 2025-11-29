# settings/__init__.py
"""Configuration data for the volleyball scraper."""

from .teams import TEAMS
from .transfers_config import OUTGOING_TRANSFERS
from .rpi_team_name_aliases import RPI_TEAM_NAME_ALIASES
from .incoming_players_data import RAW_INCOMING_TEXT

__all__ = ["TEAMS", "OUTGOING_TRANSFERS", "RPI_TEAM_NAME_ALIASES", "RAW_INCOMING_TEXT"]
