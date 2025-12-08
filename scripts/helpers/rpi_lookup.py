# rpi_lookup.py
from __future__ import annotations

from typing import Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup  # not strictly needed, but handy if you extend later
from io import StringIO

from settings import TEAMS
from .utils import normalize_text, normalize_school_key
from .logging_utils import get_logger

logger = get_logger(__name__)

RPI_URL = "https://www.ncaa.com/rankings/volleyball-women/d1/ncaa-womens-volleyball-rpi"


def build_rpi_lookup() -> Dict[str, Dict[str, str]]:
    """
    Fetch NCAA RPI table and build a lookup:
      normalized_school_key -> { 'rpi_team_name', 'rpi_rank', 'rpi_record' }
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; rpi-scraper/1.0)"}
        resp = requests.get(RPI_URL, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Could not fetch RPI page from %s: %s", RPI_URL, e)
        return {}

    # Pandas >= 2.2 wants a file-like object for literal HTML
    try:
        tables = pd.read_html(StringIO(resp.text))
    except Exception as e:
        logger.warning("Could not parse RPI tables via read_html: %s", e)
        return {}

    if not tables:
        logger.warning("No tables found on RPI page.")
        return {}

    rpi_df = None

    # Try to detect the appropriate table by columns
    for df in tables:
        cols = [str(c).strip().lower() for c in df.columns]
        has_rank = any("rank" in c for c in cols)
        has_record = any("record" in c for c in cols)
        has_teamish = any(
            ("team" in c) or ("school" in c) or ("institution" in c)
            for c in cols
        )
        if has_rank and has_record and has_teamish:
            rpi_df = df
            break

    # Fallback: just use the first table
    if rpi_df is None:
        rpi_df = tables[0]

    # Map whatever columns they used into "rank", "record", "team"
    col_map = {}
    for c in rpi_df.columns:
        lc = str(c).strip().lower()
        if "rank" in lc:
            col_map[c] = "rank"
        elif "record" in lc:
            col_map[c] = "record"
        elif "team" in lc or "school" in lc or "institution" in lc:
            col_map[c] = "team"

    rpi_df = rpi_df.rename(columns=col_map)

    if "team" not in rpi_df.columns:
        logger.warning(
            "RPI table has no recognizable team/school column. Columns were: %s",
            list(rpi_df.columns),
        )
        return {}

    # Drop rows with no team name
    rpi_df = rpi_df.dropna(subset=["team"])

    lookup: Dict[str, Dict[str, str]] = {}
    
    # Build reverse alias map: normalized RPI name -> canonical team name
    rpi_to_team: Dict[str, str] = {}
    for t in TEAMS:
        canon = normalize_text(t.get("team", ""))
        if canon:
            rpi_to_team[canon] = t["team"]
        for alias in t.get("team_name_aliases", []) or []:
            alias_norm = normalize_text(alias)
            if alias_norm:
                rpi_to_team[alias_norm] = t["team"]

    for _, row in rpi_df.iterrows():
        raw_name_norm = normalize_text(row["team"])
        if not raw_name_norm:
            continue

        rank_raw = normalize_text(row.get("rank", ""))
        record = normalize_text(row.get("record", ""))

        try:
            rank_val = int(float(rank_raw))
        except Exception:
            rank_val = None

        # Map RPI team name to your team config name using reversed aliases
        mapped_name = rpi_to_team.get(raw_name_norm, raw_name_norm)
        key = normalize_school_key(mapped_name)

        lookup[key] = {
            "rpi_team_name": raw_name_norm,
            "rpi_rank": rank_val,
            "rpi_record": record,
        }

    logger.info(
        "Built RPI lookup with %d teams from NCAA RPI page %s",
        len(lookup),
        RPI_URL,
    )
    return lookup
