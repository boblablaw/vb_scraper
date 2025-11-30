# scraper package
# Core scraping modules for D1 Women's Volleyball data collection

from .utils import (
    fetch_html,
    normalize_text,
    normalize_player_name,
    normalize_class,
    normalize_height,
    normalize_school_key,
    extract_position_codes,
    is_graduating,
    class_next_year,
    canonical_name,
    excel_protect_record,
    excel_protect_phone,
    excel_unprotect,
)

from .roster import parse_roster
from .stats import build_stats_lookup, attach_stats_to_player
from .coaches import find_coaches_page_url, parse_coaches_from_html, pack_coaches_for_row
from .transfers import (
    is_outgoing_transfer,
    is_incoming_transfer,
    get_incoming_setters_for_team,
    get_incoming_pin_hitters_for_team,
    get_incoming_middles_for_team,
    get_incoming_def_specialists_for_team,
)
from .rpi_lookup import build_rpi_lookup
from .team_analysis import analyze_team
from .labels import format_incoming_player_label, format_returning_player_label

__all__ = [
    # Utils
    "fetch_html",
    "normalize_text",
    "normalize_player_name",
    "normalize_class",
    "normalize_height",
    "normalize_school_key",
    "extract_position_codes",
    "is_graduating",
    "class_next_year",
    "canonical_name",
    "excel_protect_record",
    "excel_protect_phone",
    "excel_unprotect",
    # Roster
    "parse_roster",
    # Stats
    "build_stats_lookup",
    "attach_stats_to_player",
    # Coaches
    "find_coaches_page_url",
    "parse_coaches_from_html",
    "pack_coaches_for_row",
    # Transfers
    "is_outgoing_transfer",
    "is_incoming_transfer",
    "get_incoming_setters_for_team",
    "get_incoming_pin_hitters_for_team",
    "get_incoming_middles_for_team",
    "get_incoming_def_specialists_for_team",
    # RPI
    "build_rpi_lookup",
    # Team Analysis
    "analyze_team",
    # Labels
    "format_incoming_player_label",
    "format_returning_player_label",
]
