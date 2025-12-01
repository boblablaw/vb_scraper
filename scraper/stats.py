# stats.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO

from .utils import canonical_name, normalize_text
from .logging_utils import get_logger

logger = get_logger(__name__)


def column_key(col: Any) -> str:
    """
    Normalize multi-index / weird column labels to a flat lowercase key.
    """
    if isinstance(col, tuple):
        parts = [normalize_text(x) for x in col if x is not None]
        for p in reversed(parts):
            lp = p.lower()
            if lp and not lp.startswith("unnamed"):
                return lp
        return parts[-1].lower() if parts else ""
    else:
        return normalize_text(col).lower()


def pick_sidearm_offense_defense_tables(
    soup: BeautifulSoup,
) -> Tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    Extract SIDEARM NextGen "offensiveStats" and "defensiveStats" tables from a soup.
    Returns (offense_df, defense_df), each possibly None.
    """
    offense_df = None
    defense_df = None

    # Offensive table
    offense_table = soup.find("table", class_="offensiveStats")
    if offense_table:
        try:
            # Wrap literal HTML in StringIO to avoid FutureWarning
            offense_df = pd.read_html(StringIO(str(offense_table)))[0]
        except Exception as e:
            logger.debug("Failed to parse offensiveStats table: %s", e)

    # Defensive table
    defense_table = soup.find("table", class_="defensiveStats")
    if defense_table:
        try:
            # Wrap literal HTML in StringIO to avoid FutureWarning
            defense_df = pd.read_html(StringIO(str(defense_table)))[0]
        except Exception as e:
            logger.debug("Failed to parse defensiveStats table: %s", e)

    return offense_df, defense_df


def fetch_stats_tables(url: str) -> List[pd.DataFrame] | None:
    """
    Fetch a stats page and return a list of pandas DataFrames.

    Behavior:
      1) If SIDEARM NextGen "s-table--player-stats" is detected, try to use
         offensiveStats / defensiveStats tables via pick_sidearm_offense_defense_tables.
      2) Otherwise, fall back to pd.read_html over the whole page.
    """
    if not url:
        return None

    logger.info("Fetching stats tables: %s", url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; stats-scraper/1.4)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    # Detect SIDEARM NextGen player stats blocks
    has_nextgen = bool(soup.select("table.s-table--player-stats"))
    if has_nextgen:
        offense, defense = pick_sidearm_offense_defense_tables(soup)
        out: List[pd.DataFrame] = []
        if offense is not None:
            logger.debug("Found SIDEARM Offensive stats table.")
            out.append(offense)
        if defense is not None:
            logger.debug("Found SIDEARM Defensive stats table.")
            out.append(defense)
        if out:
            return out

    # Fallback: read all tables on the page
    try:
        # Wrap literal HTML in StringIO to avoid FutureWarning
        tables = pd.read_html(StringIO(html))
        logger.info("Found %d table(s) on stats page via read_html.", len(tables))
        return tables
    except Exception as e:
        logger.debug("Could not parse stats via read_html: %s", e)
        return None


def pick_player_stats_table(tables: List[pd.DataFrame]) -> pd.DataFrame | None:
    """
    Heuristic to pick a "player stats" table from a list of DataFrames.
    Looks for a table that has a player/name column and an assist-like column.
    """
    if not tables:
        return None

    for i, df in enumerate(tables):
        flat_cols = [column_key(c) for c in df.columns]
        has_player = any("player" in c or "name" in c for c in flat_cols)
        has_assist = any(c == "a" or c in {"ast", "a/s"} or "assist" in c for c in flat_cols)
        if has_player and has_assist:
            logger.info("Using stats table index %d as player stats.", i)
            return df

    logger.warning(
        "Could not automatically find a player stats table; using table 0 as fallback."
    )
    return tables[0]


def normalize_stats_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize columns of a stats DataFrame into consistent snake_case-like names.
    For example:
      - 'Player' / 'Name' -> 'player'
      - 'K' -> 'kills'
      - 'A' -> 'assists'
      - 'D' -> 'digs'
      - etc.
    """
    flat_cols = [column_key(c) for c in df.columns]
    df.columns = flat_cols

    col_map: Dict[str, str] = {}
    for cl in flat_cols:
        new_name = cl

        if cl in {"#", "no", "number"}:
            new_name = "number"
        elif "player" in cl or "name" in cl:
            new_name = "player"
        elif cl == "sp":
            new_name = "sets_played"
        elif cl == "mp":
            new_name = "matches_played"
        elif cl == "ms":
            new_name = "matches_started"
        elif cl == "gp":
            new_name = "games_played"
        elif cl == "gs":
            new_name = "games_started"

        elif cl == "pts":
            new_name = "points"
        elif cl in {"pts/s", "pt/s", "points/set"}:
            new_name = "points_per_set"
        elif cl == "k":
            new_name = "kills"
        elif cl in {"k/s", "kills/set"}:
            new_name = "kills_per_set"
        elif cl == "e":
            new_name = "attack_errors"
        elif cl == "ta":
            new_name = "total_attacks"
        elif cl == "pct" or "pct" in cl:
            new_name = "hitting_pct"

        elif cl == "a":
            new_name = "assists"
        elif cl in {"a/s", "ast/set", "assists/set"}:
            new_name = "assists_per_set"

        elif cl == "sa":
            new_name = "aces"
        elif cl in {"sa/s", "aces/set"}:
            new_name = "aces_per_set"
        elif cl == "se":
            new_name = "service_errors"
        elif cl == "re":
            new_name = "reception_errors"

        elif cl in {"d", "dig"}:
            new_name = "digs"
        elif cl in {"d/s", "digs/set"}:
            new_name = "digs_per_set"

        elif cl == "bs":
            new_name = "block_solos"
        elif cl == "ba":
            new_name = "block_assists"
        elif cl in {"tb", "blk"}:
            new_name = "total_blocks"
        elif cl in {"blk/s", "blocks/set"}:
            new_name = "blocks_per_set"

        elif cl == "bhe":
            new_name = "ball_handling_errors"

        col_map[cl] = new_name

    df = df.rename(columns=col_map)
    logger.debug("Stats columns after normalization: %s", list(df.columns))
    return df


def _looks_like_offense_table(df: pd.DataFrame) -> bool:
    """
    Detect if a stats table looks like an offensive table (kills, points, assists, etc.).
    """
    flat = [column_key(c) for c in df.columns]
    s = set(flat)

    has_player = any("player" in c or "name" in c for c in flat)
    if not has_player:
        return False

    offense_markers = {
        "k", "kills", "k/s", "kills/set",
        "pts", "pts/s", "points", "points/set",
        "a", "assists", "a/s", "assists/set",
        "sa", "aces", "sa/s", "aces/set",
        "pct", "hitting_pct",
    }
    return bool(s & offense_markers)


def _looks_like_defense_table(df: pd.DataFrame) -> bool:
    """
    Detect if a stats table looks like a defensive table (digs, blocks, etc.).
    """
    flat = [column_key(c) for c in df.columns]
    s = set(flat)

    has_player = any("player" in c or "name" in c for c in flat)
    if not has_player:
        return False

    defense_markers = {
        "d", "dig", "digs", "d/s", "digs/set",
        "re", "recept", "reception_errors",
        "bs", "ba", "tb", "blk",
        "blk/s", "blocks/set",
        "bhe",
    }
    return bool(s & defense_markers)


def build_stats_lookup(stats_url: str) -> Dict[str, Dict[str, Any]]:
    """
    Build a lookup:
        canonical_player_name -> full stats row (offense + defense if available).

    Behavior:
      - Calls fetch_stats_tables(stats_url).
      - Scans all returned tables for "offense-like" and "defense-like" player tables.
      - If both are found, normalize and outer-merge on 'player'.
      - If only one is found, use that one.
      - If none match, fall back to a single player stats table via pick_player_stats_table().
    """
    if not stats_url:
        return {}

    tables = None
    try:
        tables = fetch_stats_tables(stats_url)
    except Exception as e:
        logger.warning("Could not fetch stats from %s: %s", stats_url, e)
        
        # Try fallback URLs if the original fails
        fallback_urls = []
        
        # If URL ends with /2025, try /2024 and without year
        if stats_url.endswith("/2025"):
            base_url = stats_url[:-5]  # Remove /2025
            fallback_urls.append(base_url + "/2024")
            fallback_urls.append(base_url)
        # If URL ends with /2024, try without year
        elif stats_url.endswith("/2024"):
            fallback_urls.append(stats_url[:-5])
        
        # Try each fallback URL
        for fallback_url in fallback_urls:
            logger.info("Trying fallback stats URL: %s", fallback_url)
            try:
                tables = fetch_stats_tables(fallback_url)
                if tables:
                    logger.info("Successfully fetched stats from fallback URL: %s", fallback_url)
                    break
            except Exception as fallback_e:
                logger.debug("Fallback URL %s also failed: %s", fallback_url, fallback_e)
                continue
        
        if not tables:
            logger.info("Stats not available for %s - continuing without stats", stats_url)
            return {}

    if not tables:
        return {}

    offense_df_raw: pd.DataFrame | None = None
    defense_df_raw: pd.DataFrame | None = None

    # First pass: detect offense/defense tables
    for df in tables:
        if offense_df_raw is None and _looks_like_offense_table(df):
            offense_df_raw = df
        if defense_df_raw is None and _looks_like_defense_table(df):
            defense_df_raw = df

    merged_df: pd.DataFrame | None = None

    # Case A: we identified offense and/or defense tables
    if offense_df_raw is not None or defense_df_raw is not None:
        off_df = normalize_stats_columns(offense_df_raw.copy()) if offense_df_raw is not None else None
        def_df = normalize_stats_columns(defense_df_raw.copy()) if defense_df_raw is not None else None

        if (
            off_df is not None
            and def_df is not None
            and "player" in off_df.columns
            and "player" in def_df.columns
        ):
            merged_df = pd.merge(
                off_df,
                def_df,
                on="player",
                how="outer",
                suffixes=("", "_def"),
            )
            logger.info("Merged offensive + defensive stats tables on 'player'.")
            
            # Rename total_attacks_def to total_reception_attempts (TA in defensive stats = reception attempts)
            if "total_attacks_def" in merged_df.columns:
                merged_df = merged_df.rename(columns={"total_attacks_def": "total_reception_attempts"})
        elif off_df is not None:
            merged_df = off_df
        elif def_df is not None:
            merged_df = def_df

    # Case B: fallback to a single player stats table
    if merged_df is None:
        core_df = pick_player_stats_table(tables)
        if core_df is None:
            return {}
        merged_df = normalize_stats_columns(core_df)

    merged_df = merged_df.dropna(how="all")

    if "player" not in merged_df.columns:
        logger.warning("Stats table has no 'player' column after normalization.")
        return {}

    lookup: Dict[str, Dict[str, Any]] = {}
    for _, row in merged_df.iterrows():
        raw_name = str(row["player"])
        key = canonical_name(raw_name)
        if not key:
            continue
        lookup[key] = row.to_dict()

    logger.info("Built stats lookup with %d players from %s", len(lookup), stats_url)
    return lookup


def attach_stats_to_player(
    player_row: Dict[str, Any],
    stats_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Attach stats from the lookup to a player row in-place-ish.
    Does not overwrite existing non-empty values in player_row.
    """
    key = canonical_name(player_row["name"])
    stats_row = stats_lookup.get(key)
    if not stats_row:
        return player_row

    for col_name, value in stats_row.items():
        if col_name == "player":
            continue
        if col_name in player_row and player_row[col_name] not in ("", None):
            continue
        player_row[col_name] = value

    return player_row
