#!/usr/bin/env python3
"""Parse NCAA "Combined Team Statistics" PDFs (Livestats) into CSVs.

This is designed for PDFs like:
    2025-26 Kentucky Women's Volleyball
    Combined Team Statistics - All games

The script extracts the "Team Box Score" table and writes a CSV in the
`stats/` directory that is compatible with `src/merge_manual_stats.py`.

Assumptions
-----------
- PDFs live in stats/pdfs/*.pdf
- Layout has a "Team Box Score" table with header row containing:

    ## Player SP K K/S E TA PCT A A/S SA SE SA/S RE DIG DIG/S BS BA TOT/S BLK/S BE BHE PTS

- We only care about player rows (not team / opponent totals).
- Output CSV schema:
    Row 0: category headers (cosmetic only)
    Row 1: stat abbreviations (used by merge_manual_stats.py)
    Row 2+: data rows

Usage
-----
    python scripts/parse_ncaa_pdf_stats.py

Outputs files named:
    stats/<team_id>_stats.csv

where <team_id> is a normalized identifier derived from the team name
found in the PDF header line "YYYY-YY <Team Name> Women's Volleyball".
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

import sys
from pathlib import Path as _PathForSys

# Ensure project root is on sys.path when running as a script
_project_root = _PathForSys(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scraper.utils import normalize_school_key

PDF_DIR = Path("stats/pdfs")
OUT_DIR = Path("stats")

# Header row expected by merge_manual_stats.py for this format
STAT_HEADER = [
    "#",
    "Player",
    "SP",
    "K",
    "K/S",
    "E",
    "TA",
    "PCT",
    "A",
    "A/S",
    "SA",
    "SE",
    "SA/S",
    "RE",
    "DIG",
    "DIG/S",
    "BS",
    "BA",
    "BLK",   # PDF "TOT/S" column (total blocks)
    "BLK/S",  # blocks per set
    "BE",
    "BHE",
    "PTS",
]

# Cosmetic category row (row 0) – merge_manual_stats.py ignores it
CATEGORY_ROW = [
    "",        # #
    "",        # Player
    "",        # SP
    "",        # K
    "",        # K/S
    "",        # E
    "",        # TA
    "ATTACK",  # PCT
    "",        # A
    "SET",     # A/S
    "",        # SA
    "",        # SE
    "SERVE",   # SA/S
    "",        # RE
    "DIG",     # DIG
    "",        # DIG/S
    "BLOCK",   # BS
    "",        # BA
    "",        # BLK
    "",        # BLK/S
    "",        # BE
    "",        # BHE
    "PTS",     # PTS
]


def extract_team_name_from_text(text: str) -> Optional[str]:
    """Find team name from header line.

    Supports headers like:
        "2025-26 Kentucky Women's Volleyball"
        "2025 Oregon State Women's Volleyball"
    """

    pattern = re.compile(r"\d{4}(?:-\d{2})?\s+(.+?)\s+Women['’]s Volleyball")

    for line in text.splitlines():
        line = line.strip()
        m = pattern.search(line)
        if m:
            return m.group(1).strip()
    return None


def normalize_team_id(team_name: str) -> str:
    """Convert team name to a simple identifier for filenames.

    Example: "University of Kentucky" -> "kentucky".
    """

    key = normalize_school_key(team_name)  # already lowercased / simplified
    return key.replace(" ", "_")


def find_team_box_score_table(page) -> Optional[List[List[str]]]:
    """Use pdfplumber's table extraction and pick the Team Box Score table.

    The Team Box Score table may have a first row of category labels
    ("Attack", "Set", "Serve", etc.) and a second row with the real
    column headers ("Player", "SP", "K", ...). We therefore scan *all*
    rows in each table looking for a row that contains the key headers.
    """

    tables = page.extract_tables()
    for tbl in tables:
        if not tbl:
            continue
        for row in tbl:
            cells = [c or "" for c in row]
            row_str = " ".join(cells)
            if "Player" in row_str and "SP" in row_str and "K" in row_str:
                return tbl
    return None


def _parse_players_from_numeric_table_and_text(page, text: str) -> List[Dict[str, str]]:
    """Fallback parser for layouts where the header row isn't part of the table.

    This handles PDFs like the 2025 Oregon State example where:
      * `extract_tables()` returns a single 9-column table of numeric groups
      * the `# Player SP` header row is rendered as plain text, not a table row
      * each table row corresponds to one player (or "TM Team"), in the same
        order as the player summary lines in the text block.

    Strategy:
      1. Extract a *single* non-empty table via `extract_tables()`.
      2. From the page text, collect player header lines of the form
         "<#> <Name> <SP> ..." (ignoring team/total lines).
      3. Zip players with table rows by index and map the table's 9 numeric
         groups into the STAT_HEADER columns.

    If the layout does not match this structure, returns an empty list.
    """

    tables = [t for t in page.extract_tables() if t and len(t) >= 5]
    if len(tables) != 1:
        return []

    table = tables[0]

    # ---- Step 1: collect player header lines from the text ----
    player_lines: List[str] = []
    current: Optional[str] = None

    for raw_line in text.splitlines():
        line = (raw_line or "").strip()
        if not line:
            continue

        # Stop before the totals / team-statistics section so we
        # don't accidentally append summary numbers to the last
        # player's line.
        if line.startswith("Total ") or line.startswith("Opponents ") or line.startswith("Team Statistics"):
            if current:
                player_lines.append(current.strip())
                current = None
            break

        # New player line starts with jersey number at column 0
        if re.match(r"^\d+\s+", line):
            if current:
                player_lines.append(current.strip())
            current = line
        else:
            # Continuation of the current player's stats line
            if current:
                current += " " + line

    if current:
        player_lines.append(current.strip())

    players_meta: List[Dict[str, str]] = []

    for line in player_lines:
        # Ignore team / totals if they ever sneak in
        if line.startswith("TM Team") or line.startswith("Total ") or line.startswith("Opponents"):
            continue

        m = re.match(r"^(\d+)\s+(.+?)\s+(\d+)(?:\s|$)", line)
        if not m:
            continue
        jersey, name, sp = m.group(1), m.group(2), m.group(3)
        players_meta.append({"#": jersey, "Player": name, "SP": sp, "raw_line": line})

    if not players_meta:
        return []

    # Drop any trailing meta players if table has fewer rows (e.g. TM Team)
    if len(players_meta) > len(table):
        players_meta = players_meta[: len(table)]

    # ---- Step 2: map numeric groups from table rows into STAT_HEADER ----

    def split_group(cell: Optional[str], expected: int) -> List[str]:
        toks = (cell or "").replace("\n", " ").split()
        if len(toks) < expected:
            toks += [""] * (expected - len(toks))
        return toks[:expected]

    players: List[Dict[str, str]] = []

    for idx, meta in enumerate(players_meta):
        row = table[idx]
        cells = [c if isinstance(c, str) else "" for c in row]
        # Expect 9 columns: [#, Attack, Set, Serve, RE, DIG, BLOCK, BHE, PTS]
        if len(cells) < 9:
            continue

        attack = split_group(cells[1], 5)   # K, K/S, E, TA, PCT
        set_g = split_group(cells[2], 2)    # A, A/S
        serve = split_group(cells[3], 3)    # SA, SE, SA/S
        re_g = split_group(cells[4], 1)     # RE
        dig = split_group(cells[5], 2)      # DIG, DIG/S
        block = split_group(cells[6], 5)    # BS, BA, BLK, BLK/S, BE
        bhe = split_group(cells[7], 1)      # BHE
        pts = split_group(cells[8], 1)      # PTS (may be empty for some rows)

        values = [
            meta["#"],
            meta["Player"],
            meta["SP"],
            *attack,
            *set_g,
            *serve,
            *re_g,
            *dig,
            *block,
            *bhe,
            *pts,
        ]

        if len(values) != len(STAT_HEADER):
            # Layout mismatch; bail out rather than producing wrong data
            return []

        players.append({col: val for col, val in zip(STAT_HEADER, values)})

    # Use the raw text lines to correct BE, BHE, PTS, which can be
    # misaligned or missing in the table extraction for some rows.
    for player, meta in zip(players, players_meta):
        raw_line = meta.get("raw_line", "")
        if not raw_line:
            continue
        nums = re.findall(r"-?\d+(?:\.\d+)?", raw_line)
        if len(nums) < 3:
            continue
        # Last three numeric tokens are BE, BHE, PTS in these PDFs.
        be, bhe_val, pts_val = nums[-3], nums[-2], nums[-1]
        player["BE"] = be
        player["BHE"] = bhe_val
        player["PTS"] = pts_val

    return players


def parse_player_rows(table: List[List[str]]) -> List[Dict[str, str]]:
    """Convert Team Box Score table into list of player rows.

    We first locate the header row (the one containing "Player", "SP", "K"),
    then map the PDF columns into STAT_HEADER and drop total rows.
    """

    if not table:
        return []

    # Find the header row index (may be row 1 if row 0 is category labels)
    header_idx = 0
    for i, row in enumerate(table):
        upper = [(c or "").upper() for c in row]
        if "PLAYER" in upper and "SP" in upper and "K" in upper:
            header_idx = i
            break

    header = [c or "" for c in table[header_idx]]

    # Clean up first header cell: "##" -> "#"
    if header and header[0].startswith("#"):
        header[0] = "#"

    # Build index map from the PDF header to column indices
    idx_map: Dict[str, int] = {}
    for i, name in enumerate(header):
        n = (name or "").strip().upper()
        idx_map[n] = i

    # Mapping from our STAT_HEADER names to header labels in the PDF
    pdf_name_for: Dict[str, str] = {
        "#": "#",
        "Player": "PLAYER",
        "SP": "SP",
        "K": "K",
        "K/S": "K/S",
        "E": "E",
        "TA": "TA",
        "PCT": "PCT",
        "A": "A",
        "A/S": "A/S",
        "SA": "SA",
        "SE": "SE",
        "SA/S": "SA/S",
        "RE": "RE",
        "DIG": "DIG",
        "DIG/S": "DIG/S",
        "BS": "BS",
        "BA": "BA",
        # PDF header prints 'TOT/S' but values act as total blocks
        "BLK": "TOT/S",
        "BLK/S": "BLK/S",
        "BE": "BE",
        "BHE": "BHE",
        "PTS": "PTS",
    }

    players: List[Dict[str, str]] = []

    for row in table[1:]:
        if not row:
            continue
        cells = [c.strip() if isinstance(c, str) else "" for c in row]
        if len(cells) < 4:
            continue

        jersey = cells[0]
        if not jersey or not jersey[0].isdigit():
            # Skip non-player rows
            continue

        name = cells[1]
        name_upper = name.upper()
        if "TOTAL" in name_upper or "OPPONENT" in name_upper:
            # Skip team total / opponent rows if they sneak in here
            continue

        player_data: Dict[str, str] = {}
        for out_col in STAT_HEADER:
            pdf_col = pdf_name_for.get(out_col)
            if pdf_col is None:
                player_data[out_col] = ""
                continue
            idx = idx_map.get(pdf_col)
            value = cells[idx] if idx is not None and idx < len(cells) else ""
            player_data[out_col] = value

        players.append(player_data)

    return players


def parse_pdf(path: Path) -> None:
    print(f"Parsing {path}...")

    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""

        team_name = extract_team_name_from_text(text)
        if not team_name:
            raise RuntimeError(f"Could not find team name in {path}")

        team_id = normalize_team_id(team_name)

        # First try the standard table+header-based parser.
        table = find_team_box_score_table(page)
        players: List[Dict[str, str]] = []
        if table:
            players = parse_player_rows(table)

        # Fallback for layouts where the header row isn't part of the table
        # (e.g., Oregon State 2025 PDF).
        if not players:
            players = _parse_players_from_numeric_table_and_text(page, text)

        if not players:
            raise RuntimeError(f"No player rows parsed from {path}")

    out_path = OUT_DIR / f"{team_id}_stats.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Team: {team_name} -> id '{team_id}'")
    print(f"  Players parsed: {len(players)}")
    print(f"  Writing CSV: {out_path}")

    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CATEGORY_ROW)
        writer.writerow(STAT_HEADER)
        for p in players:
            writer.writerow([p.get(col, "") for col in STAT_HEADER])


def main() -> None:
    if not PDF_DIR.exists():
        print(f"PDF directory not found: {PDF_DIR}")
        return

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {PDF_DIR}")
        return

    print(f"Found {len(pdf_files)} PDF(s) in {PDF_DIR}")
    for path in pdf_files:
        try:
            parse_pdf(path)
        except Exception as e:
            print(f"ERROR processing {path.name}: {e}")


if __name__ == "__main__":
    main()
