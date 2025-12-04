# stats.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
from urllib.parse import urljoin
import json

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


def fetch_wmt_stats_api(team_id: str) -> pd.DataFrame | None:
    """
    Fetch player stats from the public WMT API for a given team_id.
    Maps fields to the standard short-hand stat headers used elsewhere.
    """
    api_url = f"https://api.wmt.games/api/statistics/teams/{team_id}/players?per_page=150"
    try:
        logger.info("Fetching WMT API stats: %s", api_url)
        resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        data = payload if isinstance(payload, list) else payload.get("data", [])
        if not data:
            logger.warning("WMT API returned no player data for team_id=%s", team_id)
            return None

        rows: List[Dict[str, Any]] = []
        for p in data:
            stats = ((p.get("statistic") or {}).get("data") or {}).get("season", {})
            if isinstance(stats, list):
                stats = stats[0] if stats else {}
            cols = stats.get("columns") if isinstance(stats, dict) else []
            if not cols:
                continue
            stat = cols[0].get("statistic", {})

            sets_played = stat.get("sSets")
            points = stat.get("sPoints")
            digs = stat.get("sDigs")
            attempts = stat.get("sReturnAttempts")
            rec_errors = stat.get("sReturnErrors")

            row = {
                "Player": f"{p.get('first_name','').strip()} {p.get('last_name','').strip()}".strip(),
                "MS": "",  # matches_started not provided
                "MP": stat.get("sIndMatchesPlayed", ""),
                "SP": sets_played if sets_played is not None else "",
                "PTS": points if points is not None else "",
                "PTS/S": round(points / sets_played, 2) if points not in (None, "") and sets_played not in (None, 0, "") else "",
                "K": stat.get("sKills", ""),
                "K/S": stat.get("sKillsPerGame", ""),
                "AE": stat.get("sErrors", ""),
                "TA": stat.get("sTotalAttacks", ""),
                "HIT%": stat.get("sAttackPCT", ""),
                "A": stat.get("sAssists", ""),
                "A/S": stat.get("sAssistsPerGame", ""),
                "SA": stat.get("sAces", ""),
                "SA/S": stat.get("sAcesPerGame", ""),
                "SE": stat.get("sServiceErrors", ""),
                "D": digs if digs is not None else "",
                "D/S": stat.get("sDigsPerGame", ""),
                "RE": rec_errors if rec_errors is not None else "",
                "TRE": attempts if attempts is not None else "",
                "Rec%": round((attempts - rec_errors) / attempts, 3) if attempts not in (None, 0, "") and rec_errors not in (None, "") else "",
                "BS": stat.get("sBlockSolos", ""),
                "BA": stat.get("sBlockAssists", ""),
                "TB": stat.get("sTotalBlocks", ""),
                "B/S": stat.get("sTotalBlocksPerGame", ""),
                "BHE": stat.get("sBallHandlingErrors", ""),
            }
            rows.append(row)

        if not rows:
            logger.warning("WMT API returned players but no season stats for team_id=%s", team_id)
            return None

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning("Failed to fetch WMT API stats for team_id=%s: %s", team_id, e)
        return None


def fetch_stats_tables(url: str) -> List[pd.DataFrame] | None:
    """
    Fetch a stats page and return a list of pandas DataFrames.

    Behavior:
      0) If the URL is the ACC services endpoint (conf_stats.ashx), fetch JSON and
         build a DataFrame from the returned player stats.
      0b) If the URL is a BoostSport/engage-api JSON endpoint, fetch JSON and map
          metrics to a stats table.
      1) If SIDEARM NextGen "s-table--player-stats" is detected, try to use
         offensiveStats / defensiveStats tables via pick_sidearm_offense_defense_tables.
      2) Otherwise, fall back to pd.read_html over the whole page.
    """
    if not url:
        return None

    # WMT Live Stats API (wmt.games stats pages)
    if "wmt.games" in url and "stats/season" in url:
        team_id_match = re.search("/season/(\\d+)", url)
        team_id = team_id_match.group(1) if team_id_match else None
        if team_id:
            df = fetch_wmt_stats_api(team_id)
            if df is not None:
                return [df]
        else:
            logger.warning("WMT stats URL missing team id: %s", url)

    # BoostSport JSON service (Big Ten engage-api.boostsport.ai)
    if "boostsport.ai" in url:
        try:
            logger.info("Fetching BoostSport JSON stats: %s", url)
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=60,  # BoostSport can be slow; give it more time
            )
            resp.raise_for_status()
            data = resp.json()
            players = data.get("data", [])
            if not players:
                logger.warning("BoostSport stats JSON returned no players.")
                return []

            rows: List[Dict[str, Any]] = []
            for p in players:
                metrics_list = p.get("data", []) or []
                metric_map = {}
                for m in metrics_list:
                    if isinstance(m, dict):
                        metric_map.update(m)

                rows.append({
                    # Match the standard stat headers used elsewhere
                    "Player": p.get("full_name", ""),
                    "MS": "",  # matches_started not provided
                    "MP": metric_map.get("gp", ""),
                    "SP": metric_map.get("periods", ""),
                    "PTS": metric_map.get("points", ""),
                    "PTS/S": metric_map.get("points_per_set", ""),
                    "K": metric_map.get("kills", ""),
                    "K/S": metric_map.get("kills_per_set", ""),
                    "AE": metric_map.get("errors", ""),  # attack errors not provided; leave blank
                    "TA": metric_map.get("attempts", ""),
                    "HIT%": metric_map.get("hitting_pct", ""),
                    "A": metric_map.get("assists", ""),
                    "A/S": metric_map.get("assists_per_set", ""),
                    "SA": metric_map.get("aces", ""),
                    "SA/S": metric_map.get("aces_per_set", ""),
                    "SE": "",  # service errors not provided
                    "D": metric_map.get("digs", ""),
                    "D/S": metric_map.get("dig_per_set", ""),
                    "RE": metric_map.get("receptions", ""),
                    "TRE": metric_map.get("attempts", ""),
                    "Rec%": metric_map.get("receive_pct", ""),
                    "BS": "",  # block solos not provided
                    "BA": "",  # block assists not provided
                    "TB": metric_map.get("blocks_pts", ""),
                    "B/S": metric_map.get("blocks_per_set", ""),
                    "BHE": metric_map.get("ball_handling_errors", ""),
                })

            df = pd.DataFrame(rows)
            return [df]
        except Exception as e:
            logger.warning("Failed to fetch BoostSport JSON stats: %s", e)
            return None

    # ACC JSON service (used for Stanford etc.)
    if "conf_stats.ashx" in url:
        try:
            logger.info("Fetching ACC JSON stats: %s", url)
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            players = data.get("players", [])
            if not players:
                logger.warning("ACC stats JSON returned no players.")
                return []

            rows: List[Dict[str, Any]] = []
            for p in players:
                att = p.get("attack_stats", {}) or {}
                per = p.get("per_set_stats", {}) or {}
                set_stats = p.get("set_stats", {}) or {}
                serve = p.get("serve_stats", {}) or {}
                defense = p.get("defense_stats", {}) or {}
                block = p.get("block_stats", {}) or {}
                misc = p.get("misc_stats", {}) or {}

                rows.append({
                    "Player": p.get("name", ""),
                    "SP": p.get("games_played", ""),
                    "K": att.get("kills", ""),
                    "K/S": per.get("kills", ""),
                    "E": att.get("errors", ""),
                    "TA": att.get("attempts", ""),
                    "PCT": att.get("hitting_pct", ""),
                    "Ast": set_stats.get("assists", ""),
                    "A/S": per.get("assists", ""),
                    "SA": serve.get("aces", ""),
                    "SA/S": per.get("aces", ""),
                    "SE": serve.get("errors", ""),
                    "PTS": misc.get("points", ""),
                    "PTS/S": per.get("points", ""),
                    "D": defense.get("digs", ""),
                    "D/S": per.get("digs", ""),
                    "RE": defense.get("receptions", ""),
                    "TRE": defense.get("attempts", ""),
                    "Rec%": defense.get("defense_pct", ""),
                    "BS": block.get("solos", ""),
                    "BA": block.get("assists", ""),
                    "TB": block.get("total", ""),
                    "B/S": per.get("blocks", ""),
                    "BHE": misc.get("ball_handling_errors", ""),
                })

            df = pd.DataFrame(rows)
            return [df]
        except Exception as e:
            logger.warning("Failed to fetch ACC JSON stats: %s", e)
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
        elif "rec" in cl and "pct" in cl:
            new_name = "reception_pct"
        elif cl == "pct" or ("pct" in cl and ("hit" in cl or "att" in cl)):
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

    def expand_wmt_urls(urls):
        """If a URL points to wmt.games, try query variants for offense/defense."""
        expanded: List[str] = []
        for u in urls:
            if not u:
                continue
            if "wmt.games" in u:
                expanded.extend(
                    [
                        u,
                        f"{u}?main=Individual&overall=Offensive",
                        f"{u}?main=Individual&overall=Defensive",
                        f"{u}?main=Individual",
                    ]
                )
            else:
                expanded.append(u)
        # Deduplicate while preserving order
        seen = set()
        uniq = []
        for u in expanded:
            if u not in seen:
                uniq.append(u)
                seen.add(u)
        return uniq

    def try_tables(urls):
        for u in urls:
            if not u:
                continue
            try:
                t = fetch_stats_tables(u)
                if t:
                    logger.info("Fetched stats tables from %s", u)
                    return t
            except Exception as e:
                logger.debug("Stats fetch failed for %s: %s", u, e)
        return None

    tables = try_tables(expand_wmt_urls([stats_url]))

    # If failed, try stripping trailing year segment
    stats_page_candidates: List[str] = [stats_url]
    if stats_url.endswith("/2025"):
        base = stats_url[:-5]
        stats_page_candidates.extend([base + "/2024", base])
    elif stats_url.endswith("/2024"):
        base = stats_url[:-5]
        stats_page_candidates.append(base)

    if not tables:
        tables = try_tables(expand_wmt_urls(stats_page_candidates[1:]))

    # If still nothing, try to discover iframe src (WMT embeds) across candidate pages
    if not tables:
        def discover_iframe_urls(page_url: str) -> List[str]:
            found: List[str] = []
            resp = requests.get(page_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            iframe = soup.find("iframe")
            iframe_src = iframe.get("src") if iframe else None
            if iframe_src:
                found.append(urljoin(page_url, iframe_src))
            for tag in soup.find_all(["iframe", "script", "link", "a"]):
                for attr in ("src", "href"):
                    val = tag.get(attr)
                    if val and "wmt.games" in val:
                        found.append(urljoin(page_url, val))
            # Also regex-scan the full HTML for wmt.games URLs in case they are embedded in scripts
            import re
            for m in re.findall(r"https?://wmt\\.games[^\"'\\s>]+", resp.text):
                found.append(urljoin(page_url, m))
            # Deduplicate while preserving order
            seen = set()
            uniq = []
            for u in found:
                if u not in seen:
                    uniq.append(u)
                    seen.add(u)
            return uniq

        expanded_candidates: List[str] = []
        for page in stats_page_candidates:
            try:
                logger.info("Attempting iframe stats discovery from %s", page)
                for base_iframe in discover_iframe_urls(page):
                    expanded_candidates.append(base_iframe)
                    expanded_candidates.append(f"{base_iframe}?main=Individual&overall=Offensive")
                    expanded_candidates.append(f"{base_iframe}?main=Individual&overall=Defensive")
            except Exception as e:
                logger.debug("Iframe stats discovery failed for %s: %s", page, e)

        if expanded_candidates:
            tables = try_tables(expand_wmt_urls(expanded_candidates))

    if not tables:
        logger.info("Stats not available for %s - continuing without stats", stats_url)
        return {}

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

    # Harmonize defensive duplicate columns (…_def) into primary columns
    def_to_primary = {
        "matches_played_def": "matches_played",
        "matches_started_def": "matches_started",
        "points_def": "points",
        "kills_def": "kills",
        "kills_per_set_def": "kills_per_set",
        "hitting_pct_def": "hitting_pct",
        "attack_errors_def": "attack_errors",
        "total_attacks_def": "total_reception_attempts",  # already handled above but keep for safety
        "assists_def": "assists",
        "assists_per_set_def": "assists_per_set",
        "aces_def": "aces",
        "aces_per_set_def": "aces_per_set",
        "service_errors_def": "service_errors",
        "digs_def": "digs",
        "digs_per_set_def": "digs_per_set",
        "reception_errors_def": "reception_errors",
        "total_reception_attempts_def": "total_reception_attempts",
        "reception_pct_def": "reception_pct",
        "block_solos_def": "block_solos",
        "block_assists_def": "block_assists",
        "total_blocks_def": "total_blocks",
        "blocks_per_set_def": "blocks_per_set",
        "ball_handling_errors_def": "ball_handling_errors",
    }

    for dcol, pcol in def_to_primary.items():
        if dcol in merged_df.columns:
            if pcol not in merged_df.columns or merged_df[pcol].isna().all():
                merged_df[pcol] = merged_df[dcol]
            merged_df = merged_df.drop(columns=[dcol])

    # Drop any remaining _def columns to avoid duplicate outputs
    def_cols = [c for c in merged_df.columns if c.endswith("_def")]
    if def_cols:
        merged_df = merged_df.drop(columns=def_cols)

    # Standardize column names to canonical internal headers (snake_case)
    canon_map = {
        "player": "player",
        "matches_played": "matches_played",
        "mp": "matches_played",
        "matches_started": "matches_started",
        "ms": "matches_started",
        "points": "points",
        "points_per_set": "points_per_set",
        "pts": "points",
        "pts/s": "points_per_set",
        "kills": "kills",
        "kills_per_set": "kills_per_set",
        "k": "kills",
        "k/s": "kills_per_set",
        "attack_errors": "attack_errors",
        "ae": "attack_errors",
        "total_attacks": "total_attacks",
        "ta": "total_attacks",
        "hitting_pct": "hitting_pct",
        "pct": "hitting_pct",
        "hit%": "hitting_pct",
        "assists": "assists",
        "ast": "assists",
        "assists_per_set": "assists_per_set",
        "a/s": "assists_per_set",
        "aces": "aces",
        "sa": "aces",
        "aces_per_set": "aces_per_set",
        "sa/s": "aces_per_set",
        "service_errors": "service_errors",
        "se": "service_errors",
        "digs": "digs",
        "d": "digs",
        "digs_per_set": "digs_per_set",
        "d/s": "digs_per_set",
        "reception_errors": "reception_errors",
        "re": "reception_errors",
        "total_reception_attempts": "total_reception_attempts",
        "tre": "total_reception_attempts",
        "reception_pct": "reception_pct",
        "rec%": "reception_pct",
        "block_solos": "block_solos",
        "bs": "block_solos",
        "block_assists": "block_assists",
        "ba": "block_assists",
        "total_blocks": "total_blocks",
        "tb": "total_blocks",
        "blocks_per_set": "blocks_per_set",
        "b/s": "blocks_per_set",
        "ball_handling_errors": "ball_handling_errors",
        "bhe": "ball_handling_errors",
    }

    rename_map = {}
    for col in merged_df.columns:
        key = col.lower()
        if key in canon_map:
            rename_map[col] = canon_map[key]
    merged_df = merged_df.rename(columns=rename_map)

    # Consolidate duplicate columns after renaming (keep first non-null per row)
    final_cols = []
    to_drop = []
    for col in merged_df.columns:
        if col in final_cols:
            continue
        dups = [c for c in merged_df.columns if c == col]
        if len(dups) > 1:
            merged_df[col] = merged_df[dups].bfill(axis=1).iloc[:, 0]
            to_drop.extend([c for c in dups if c != col])
        final_cols.append(col)
    if to_drop:
        merged_df = merged_df.drop(columns=to_drop)

    # Keep only canonical columns plus player
    preferred_order = [
        "player",
        "matches_started",
        "matches_played",
        "sets_played",
        "points",
        "points_per_set",
        "kills",
        "kills_per_set",
        "attack_errors",
        "total_attacks",
        "hitting_pct",
        "assists",
        "assists_per_set",
        "aces",
        "aces_per_set",
        "service_errors",
        "digs",
        "digs_per_set",
        "reception_errors",
        "total_reception_attempts",
        "reception_pct",
        "block_solos",
        "block_assists",
        "total_blocks",
        "blocks_per_set",
        "ball_handling_errors",
    ]
    merged_df = merged_df[[c for c in merged_df.columns if c in preferred_order]]
    merged_df = merged_df.dropna(how="all")

    merged_df = merged_df.dropna(how="all")

    if "player" not in merged_df.columns:
        logger.warning("Stats table has no 'player' column after normalization.")
        return {}

    lookup: Dict[str, Dict[str, Any]] = {}
    for _, row in merged_df.iterrows():
        raw_name = str(row["player"])
        low = raw_name.strip().lower()
        if not raw_name or low in {"nan", "team totals", "team total"} or ("team" in low and "total" in low):
            continue
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
