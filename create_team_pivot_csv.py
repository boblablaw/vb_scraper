# team_pivot_2026.py

import csv
import re
import os
from typing import Any, Dict, List

import os
from typing import List, Dict

import pandas as pd

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

INPUT_TSV = os.path.join(EXPORT_DIR, "d1_rosters_2026_with_stats_and_incoming.tsv")

OUTPUT_TSV = os.path.join(EXPORT_DIR, "d1_team_pivot_2026.tsv")
OUTPUT_CSV = os.path.join(EXPORT_DIR, "d1_team_pivot_2026.csv")

from settings import OUTGOING_TRANSFERS

def excel_unprotect(value: Any) -> str:
    """
    Convert protected Excel value ="6-2" -> 6-2.
    If not wrapped, return as string unchanged.
    """
    s = str(value).strip()
    if not s:
        return ""
    if s.startswith('="') and s.endswith('"'):
        return s[2:-1]
    return s


def first_non_empty(series: pd.Series) -> str:
    """
    Return the first non-empty, non-NaN value in a Series as a string.
    Used for team-level fields like team_rpi_rank, team_overall_record.
    """
    for v in series:
        if pd.notna(v) and str(v).strip() != "":
            return str(v)
    return ""


def to_int_safe(val: Any) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


def normalize_school_key(name: str) -> str:
    """
    Same school-key normalizer as in main_roster_scraper:
    lowercase, strip punctuation, remove words:
      'university', 'college', 'of', 'the'
    """
    s = str(name or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    stop_words = {"university", "college", "of", "the"}
    tokens = [t for t in s.split() if t and t not in stop_words]
    return " ".join(tokens)


def height_str_to_inches(h: str) -> float:
    """
    Convert '6-2' style height (optionally wrapped as ="6-2") to total inches.
    Returns NaN if not parseable.
    """
    s = str(h).strip()
    if not s:
        return float("nan")

    # Strip Excel-protection wrapper ="6-2"
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1].strip()

    # Expect "F-I"
    if "-" not in s:
        return float("nan")
    parts = s.split("-")
    if len(parts) != 2:
        return float("nan")
    try:
        feet = int(parts[0])
        inches = int(parts[1])
        return feet * 12 + inches
    except Exception:
        return float("nan")


def inches_to_height_str(inches: float) -> str:
    """
    Convert total inches back to "F' I\"" format (e.g. 71 -> 5' 11").
    """
    if pd.isna(inches):
        return ""
    inches = int(round(inches))
    feet = inches // 12
    rem = inches % 12
    return f"{feet}' {rem}\""


def lookup_player_info_by_name(df: pd.DataFrame, name: str) -> Dict[str, str]:
    """
    Given a player name, pull position + class_next_year or class from the
    full dataset. Returns {} if not found.
    """
    name_norm = str(name).strip().lower()
    if "name" not in df.columns:
        return {}

    subset = df[df["name"].str.lower() == name_norm]

    if subset.empty:
        return {}

    row = subset.iloc[0]

    pos = str(row.get("position", "")).strip()
    cls = str(row.get("class_next_year", "")).strip()
    if not cls:
        cls = str(row.get("class", "")).strip()

    return {
        "position": pos,
        "class": cls,
    }


# --- Same beautify + aliasing used by the main scraper for column headers ---

FRIENDLY_ALIASES_INPUT = {
    # Returning names
    "returning_setter_names_2026": "returning_setters",
    "returning_pin_hitter_names_2026": "returning_pins",
    "returning_middle_blocker_names_2026": "returning_middles",
    "returning_def_specialist_names_2026": "returning_defs",
    # Incoming names
    "incoming_setter_names_2026": "incoming_setters",
    "incoming_pin_hitter_names_2026": "incoming_pins",
    "incoming_middle_blocker_names_2026": "incoming_middles",
    "incoming_def_specialist_names_2026": "incoming_defs",
}


def beautify(col: str) -> str:
    """
    Convert snake_case or similar to 'Title Case' without underscores,
    and strip '2026' from the header.
    (Matches the main scraper's behavior.)
    """
    base = " ".join(word.capitalize() for word in col.replace("_", " ").split())
    base = base.replace("2026", "").strip()
    base = " ".join(base.split())
    return base


def map_friendly_headers_to_internal(df: pd.DataFrame) -> pd.DataFrame:
    """
    The main scraper wrote the TSV using beautified headers (and some aliases).
    Here we map those friendly headers back to the internal snake_case names
    this pivot script expects.
    """

    # Internal columns we actually care about reading from the TSV
    internal_cols = set([
        # base
        "team",
        "conference",
        "team_rpi_rank",
        "team_overall_record",
        "name",
        "position",
        "class",
        "class_next_year",
        "height",

        # flags
        "is_setter",
        "is_pin_hitter",
        "is_middle_blocker",
        "is_def_specialist",
        "is_graduating",
        "is_outgoing_transfer",
        "is_incoming_transfer",

        # stats
        "assists",
        "kills",
        "digs",

        # incoming positional name lists
        "incoming_setter_names_2026",
        "incoming_pin_hitter_names_2026",
        "incoming_middle_blocker_names_2026",
        "incoming_def_specialist_names_2026",

        # counts & name lists by position (from main script)
        "returning_setter_count_2026",
        "returning_setter_names_2026",
        "incoming_setter_count_2026",
        "projected_setter_count_2026",

        "returning_pin_hitter_count_2026",
        "returning_pin_hitter_names_2026",
        "incoming_pin_hitter_count_2026",
        "projected_pin_hitter_count_2026",

        "returning_middle_blocker_count_2026",
        "returning_middle_blocker_names_2026",
        "incoming_middle_blocker_count_2026",
        "projected_middle_blocker_count_2026",

        "returning_def_specialist_count_2026",
        "returning_def_specialist_names_2026",
        "incoming_def_specialist_count_2026",
        "projected_def_specialist_count_2026",

        # coaches
        "coach1_name", "coach1_title", "coach1_email", "coach1_phone",
        "coach2_name", "coach2_title", "coach2_email", "coach2_phone",
        "coach3_name", "coach3_title", "coach3_email", "coach3_phone",
        "coach4_name", "coach4_title", "coach4_email", "coach4_phone",
        "coach5_name", "coach5_title", "coach5_email", "coach5_phone",
    ])

    current_cols = set(df.columns)

    # For each internal name, compute what the main script would have used
    # as the friendly header, and if that friendly header exists, rename it back.
    rename_map: Dict[str, str] = {}
    for internal in internal_cols:
        alias = FRIENDLY_ALIASES_INPUT.get(internal, internal)
        friendly = beautify(alias)
        if friendly in current_cols and internal not in current_cols:
            rename_map[friendly] = internal

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def build_team_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one-row-per-team pivot with:
      - team + conference
      - team_rpi_rank + team_overall_record
      - returning players by position (names with class_next_year + stat)
      - incoming / outgoing transfers lists (including config-only incoming)
      - average height by position
      - coach info (coach1–coach5 name/title/email/phone)
    """

    # Make sure key columns exist as strings
    for col in [
        "team",
        "conference",
        "team_rpi_rank",
        "team_overall_record",
        "name",
        "position",
        "class",
        "class_next_year",
        "height",
        "is_setter",
        "is_pin_hitter",
        "is_middle_blocker",
        "is_def_specialist",
        "is_graduating",
        "is_outgoing_transfer",
        "is_incoming_transfer",
        "assists",
        "kills",
        "digs",
        # incoming-position name lists
        "incoming_setter_names_2026",
        "incoming_pin_hitter_names_2026",
        "incoming_middle_blocker_names_2026",
        "incoming_def_specialist_names_2026",
        # coaches
        "coach1_name", "coach1_title", "coach1_email", "coach1_phone",
        "coach2_name", "coach2_title", "coach2_email", "coach2_phone",
        "coach3_name", "coach3_title", "coach3_email", "coach3_phone",
        "coach4_name", "coach4_title", "coach4_email", "coach4_phone",
        "coach5_name", "coach5_title", "coach5_email", "coach5_phone",
    ]:
        if col not in df.columns:
            df[col] = ""

    # Ensure name is string for lookups
    df["name"] = df["name"].astype(str)

    # Ensure numeric-ish fields are at least strings
    df["team_rpi_rank"] = df["team_rpi_rank"].astype(str)
    df["team_overall_record"] = df["team_overall_record"].astype(str)

    # Cast boolean-ish columns to int (0/1) safely
    for col in [
        "is_setter",
        "is_pin_hitter",
        "is_middle_blocker",
        "is_def_specialist",
        "is_graduating",
        "is_outgoing_transfer",
        "is_incoming_transfer",
    ]:
        df[col] = df[col].apply(to_int_safe)

    # Numeric stats: assists, kills, digs
    for col in ["assists", "kills", "digs"]:
        df[col] = df[col].apply(to_int_safe)

    # Height in inches for averaging
    df["height_inches"] = df["height"].apply(height_str_to_inches)

    teams: List[Dict[str, Any]] = []

    grouped = df.groupby(["team", "conference"], dropna=False, sort=True)

    for (team, conf), g in grouped:
        g = g.copy()

        # ------- Team-level fields (RPI) -------
        rpi_rank = first_non_empty(g["team_rpi_rank"])
        rpi_record = first_non_empty(g["team_overall_record"])
        
        # ------- Determine offense type (5-1 vs 6-2) based on assists -------
        offense_type = "Unknown"
        if "assists" in g.columns:
            # Count setters with significant assists (>= 350)
            setters_with_assists = g[(g["assists"] >= 350) & (g["is_setter"] == 1)]
            num_setters_with_assists = len(setters_with_assists)
            
            if num_setters_with_assists >= 2:
                offense_type = "6-2"
            elif num_setters_with_assists == 1:
                offense_type = "5-1"
            # else remains "Unknown"

        # Normalized key for this team (for matching transfers config)
        team_key = normalize_school_key(team)

        # Transfers from the config where this team is the DESTINATION (new_team)
        incoming_cfg_only = []
        for xfer in OUTGOING_TRANSFERS:
            new_team = xfer.get("new_team", "")
            if not new_team:
                continue
            if normalize_school_key(new_team) != team_key:
                continue
            incoming_cfg_only.append(xfer)

        # ------- Masks for 2026 returning & transfers -------
        not_grad = g["is_graduating"] == 0
        not_xfer_out = g["is_outgoing_transfer"] == 0

        # Returning = on roster, not graduating, not outgoing transfer
        returning_mask = not_grad & not_xfer_out

        # Position masks
        ms_setter = g["is_setter"] == 1
        ms_pin = g["is_pin_hitter"] == 1
        ms_mb = g["is_middle_blocker"] == 1
        ms_def = g["is_def_specialist"] == 1

        # Returning players by position
        ret_setters = g[returning_mask & ms_setter]
        ret_pins = g[returning_mask & ms_pin]
        ret_mbs = g[returning_mask & ms_mb]
        ret_defs = g[returning_mask & ms_def]

        # Incoming / outgoing transfers from roster flags
        incoming_transfers = g[g["is_incoming_transfer"] == 1]
        outgoing_transfers = g[g["is_outgoing_transfer"] == 1]

        # ------- Helpers for formatted name lists -------

        def format_returning_players(block: pd.DataFrame, stat_col: str) -> str:
            """
            "Regan Kassel - So. (592)"
            """
            rows = []
            for _, row in block.iterrows():
                name = str(row["name"]).strip()
                cls = str(row["class_next_year"]).strip()
                stat_val = to_int_safe(row.get(stat_col, 0))
                # If class_next_year is empty, fall back to class
                if not cls:
                    cls = str(row.get("class", "")).strip()
                if not name:
                    continue
                rows.append(f"{name} - {cls} ({stat_val})")
            return ", ".join(rows)

        def format_transfer_players(block: pd.DataFrame) -> str:
            """
            "Molly Beatty (S - So.), Grace Thomas (MB - R-Jr.)"
            """
            rows = []
            for _, row in block.iterrows():
                name = str(row["name"]).strip()
                pos = str(row["position"]).strip()
                cls = str(row["class_next_year"]).strip()
                if not cls:
                    cls = str(row.get("class", "")).strip()
                if not name:
                    continue
                rows.append(f"{name} ({pos} - {cls})")
            return ", ".join(rows)

        # Setters: stat = assists
        returning_setter_names = format_returning_players(ret_setters, "assists")

        # Pins: stat = kills
        returning_pin_names = format_returning_players(ret_pins, "kills")

        # Middles: stat = kills
        returning_mb_names = format_returning_players(ret_mbs, "kills")

        # DS / Libero: stat = digs
        returning_def_names = format_returning_players(ret_defs, "digs")

        # Transfers from roster flags
        incoming_transfer_names = format_transfer_players(incoming_transfers)
        outgoing_transfer_names = format_transfer_players(outgoing_transfers)

        # ----- Append config-based incoming transfers in the same format -----
        extra_rows = []
        existing_incoming_names = {
            str(n).strip().lower() for n in incoming_transfers["name"]
        }

        for xfer in incoming_cfg_only:
            nm = str(xfer.get("name", "")).strip()
            if not nm or nm.lower() in existing_incoming_names:
                continue

            # Lookup position/class from the full DF (source roster)
            info = lookup_player_info_by_name(df, nm)
            pos = info.get("position", "")
            cls = info.get("class", "")

            extra_rows.append(f"{nm} ({pos} - {cls})")

        if extra_rows:
            extra_str = ", ".join(extra_rows)
            if incoming_transfer_names:
                incoming_transfer_names = incoming_transfer_names + ", " + extra_str
            else:
                incoming_transfer_names = extra_str

        # ------- Simple counts (use max; they are constant per team from main script) -------

        def max_int(col: str) -> int:
            if col not in g.columns:
                return 0
            return max([to_int_safe(v) for v in g[col].unique()] + [0])

        row: Dict[str, Any] = {
            "team": team,
            "conference": conf,
            "team_rpi_rank": rpi_rank,
            "team_overall_record": rpi_record,
            "offense_type": offense_type,
        }

        # Position counts (from main script columns)
        for col in [
            "returning_setter_count_2026",
            "incoming_setter_count_2026",
            "projected_setter_count_2026",
            "returning_pin_hitter_count_2026",
            "incoming_pin_hitter_count_2026",
            "projected_pin_hitter_count_2026",
            "returning_middle_blocker_count_2026",
            "incoming_middle_blocker_count_2026",
            "projected_middle_blocker_count_2026",
            "returning_def_specialist_count_2026",
            "incoming_def_specialist_count_2026",
            "projected_def_specialist_count_2026",
        ]:
            if col in g.columns:
                row[col] = max_int(col)
            else:
                row[col] = 0

        # Name lists (returning by position)
        row["returning_setter_names_2026"] = returning_setter_names
        row["returning_pin_hitter_names_2026"] = returning_pin_names
        row["returning_middle_blocker_names_2026"] = returning_mb_names
        row["returning_def_specialist_names_2026"] = returning_def_names

        # Transfers (incoming/outgoing)
        row["incoming_transfer_names"] = incoming_transfer_names
        row["outgoing_transfer_names"] = outgoing_transfer_names

        # Incoming positional players (from main script; same for all rows on team)
        for col in [
            "incoming_setter_names_2026",
            "incoming_pin_hitter_names_2026",
            "incoming_middle_blocker_names_2026",
            "incoming_def_specialist_names_2026",
        ]:
            if col in g.columns:
                row[col] = first_non_empty(g[col])
            else:
                row[col] = ""

        # Average height (overall & by pos) in nice "5' 11"" format
        def avg_height_for_mask(mask: pd.Series) -> str:
            h = g.loc[mask, "height_inches"]
            if h.empty:
                return ""
            return inches_to_height_str(h.mean())

        row["avg_height_team"] = avg_height_for_mask(g["height_inches"].notna())
        row["avg_height_setters"] = avg_height_for_mask(ms_setter & g["height_inches"].notna())
        row["avg_height_pins"] = avg_height_for_mask(ms_pin & g["height_inches"].notna())
        row["avg_height_middles"] = avg_height_for_mask(ms_mb & g["height_inches"].notna())
        row["avg_height_defs"] = avg_height_for_mask(ms_def & g["height_inches"].notna())

        # ------- Coaches: first non-empty per team -------

        coach_fields = [
            "coach1_name", "coach1_title", "coach1_email", "coach1_phone",
            "coach2_name", "coach2_title", "coach2_email", "coach2_phone",
            "coach3_name", "coach3_title", "coach3_email", "coach3_phone",
            "coach4_name", "coach4_title", "coach4_email", "coach4_phone",
            "coach5_name", "coach5_title", "coach5_email", "coach5_phone",
        ]

        for cf in coach_fields:
            if cf in g.columns:
                row[cf] = first_non_empty(g[cf])
            else:
                row[cf] = ""

        teams.append(row)

    pivot_df = pd.DataFrame(teams)

    # Make sure RPI record stays as text (not date)
    pivot_df["team_overall_record"] = pivot_df["team_overall_record"].astype(str)

    return pivot_df


def main():
    # Read the main file *as strings* and, for TSV, with delimiter="\t"
    df = pd.read_csv(INPUT_TSV, sep="\t", dtype=str, keep_default_na=False)

    # Map friendly column headers (from main scraper) back to internal names
    df = map_friendly_headers_to_internal(df)

    pivot_df = build_team_pivot(df)

    # ---- INTERNAL COLUMN ORDER (snake_case) ----
    ordered = [
        # Base info
        "team",
        "conference",
        "team_rpi_rank",
        "team_overall_record",
        "offense_type",

        # --- SETTERS ---
        "returning_setter_count_2026",
        "returning_setter_names_2026",
        "incoming_setter_count_2026",
        "incoming_setter_names_2026",
        "projected_setter_count_2026",

        # --- PIN HITTERS ---
        "returning_pin_hitter_count_2026",
        "returning_pin_hitter_names_2026",
        "incoming_pin_hitter_count_2026",
        "incoming_pin_hitter_names_2026",
        "projected_pin_hitter_count_2026",

        # --- MIDDLE BLOCKERS ---
        "returning_middle_blocker_count_2026",
        "returning_middle_blocker_names_2026",
        "incoming_middle_blocker_count_2026",
        "incoming_middle_blocker_names_2026",
        "projected_middle_blocker_count_2026",

        # --- DEFENSIVE SPECIALISTS / LIBEROS ---
        "returning_def_specialist_count_2026",
        "returning_def_specialist_names_2026",
        "incoming_def_specialist_count_2026",
        "incoming_def_specialist_names_2026",
        "projected_def_specialist_count_2026",

        # Transfers
        "incoming_transfer_names",
        "outgoing_transfer_names",

        # Heights
        "avg_height_team",
        "avg_height_setters",
        "avg_height_pins",
        "avg_height_middles",
        "avg_height_defs",

        # Coaches
        "coach1_name", "coach1_title", "coach1_email", "coach1_phone",
        "coach2_name", "coach2_title", "coach2_email", "coach2_phone",
        "coach3_name", "coach3_title", "coach3_email", "coach3_phone",
        "coach4_name", "coach4_title", "coach4_email", "coach4_phone",
        "coach5_name", "coach5_title", "coach5_email", "coach5_phone",
    ]

    # Append leftovers in case new columns were added upstream
    existing_cols = list(pivot_df.columns)
    leftovers = [c for c in existing_cols if c not in ordered]
    ordered += leftovers

    pivot_df = pivot_df[ordered]

    # ---- BUILD RAW DF FOR CSV (UNPROTECTED VALUES) ----
    raw_df = pivot_df.copy()

    if "team_overall_record" in raw_df.columns:
        raw_df["team_overall_record"] = raw_df["team_overall_record"].apply(excel_unprotect)

    for col in raw_df.columns:
        if col.endswith("_phone"):
            raw_df[col] = raw_df[col].apply(excel_unprotect)

    # ---- RENAME TO FRIENDLY NAMES (same mapping for TSV & CSV) ----
    friendly_names = {
        # Returning names (by position)
        "returning_setter_names_2026": "returning_setters",
        "returning_pin_hitter_names_2026": "returning_pins",
        "returning_middle_blocker_names_2026": "returning_middles",
        "returning_def_specialist_names_2026": "returning_defs",

        # Incoming names (by position)
        "incoming_setter_names_2026": "incoming_setters",
        "incoming_pin_hitter_names_2026": "incoming_pins",
        "incoming_middle_blocker_names_2026": "incoming_middles",
        "incoming_def_specialist_names_2026": "incoming_defs",

        # Transfers
        "incoming_transfer_names": "incoming_transfers",
        "outgoing_transfer_names": "outgoing_transfers",
    }

    pivot_df = pivot_df.rename(columns=friendly_names)
    raw_df = raw_df.rename(columns=friendly_names)

    # ---- BEAUTIFY ALL COLUMN HEADERS ----
    def beautify_out(col: str) -> str:
        """
        Convert snake_case (or similar) names to 'Title Case' without underscores
        and strip '2026' from the header.
        """
        return beautify(col)

    pivot_df = pivot_df.rename(columns={c: beautify_out(c) for c in pivot_df.columns})
    raw_df = raw_df.rename(columns={c: beautify_out(c) for c in raw_df.columns})

    # ---- WRITE TSV (SAFE VALUES) ----
    pivot_df.to_csv(OUTPUT_TSV, sep="\t", index=False, quoting=csv.QUOTE_MINIMAL)

    # ---- WRITE CSV (RAW VALUES) ----
    raw_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)

    print(f"Wrote team pivot to {OUTPUT_TSV} and {OUTPUT_CSV}")
    print("Columns:", list(pivot_df.columns))


if __name__ == "__main__":
    main()
