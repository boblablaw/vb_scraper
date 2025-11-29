# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a web scraper for Division 1 Women's Volleyball programs. It collects roster data, player statistics, coach information, incoming transfers, and RPI rankings from NCAA D1 volleyball team websites, then aggregates them into CSV/TSV exports for analysis.

## Common Commands

### Running the Scraper

```bash
# Activate virtual environment
source venv/bin/activate

# Run the main scraper (generates per-player data)
python run_scraper.py

# Generate team pivot table (aggregated team-level data)
python team_pivot.py

# Export transfer data to CSV
python export_transfers.py
```

### Virtual Environment

```bash
# Create venv (if needed)
python3.13 -m venv venv

# Activate
source venv/bin/activate

# Install dependencies
pip install pandas requests beautifulsoup4
```

## Output Files

All outputs are written to the `exports/` directory:

- `d1_rosters_2026_with_stats_and_incoming.csv` / `.tsv` — Per-player data (main output)
- `d1_team_pivot_2026.csv` / `.tsv` — Aggregated team-level data
- `outgoing_transfers.csv` — Exported transfer data
- `scraper.log` — Detailed execution log

## Architecture

### Data Flow

```
settings/teams.py (team URLs) 
    → run_scraper.py (orchestrator)
        → team_analysis.py (per-team processing)
            ├─ roster.py (parse roster HTML)
            ├─ stats.py (parse stats tables)
            ├─ coaches.py (extract coach info)
            ├─ transfers.py (match transfer data)
            ├─ incoming_players.py (incoming player list)
            ├─ rpi_lookup.py (fetch RPI rankings)
            └─ settings/ (config: teams, transfers, RPI aliases)
    → exports/d1_rosters_*.csv|tsv

team_pivot.py (reads TSV, aggregates by team)
    → exports/d1_team_pivot_*.csv|tsv
```

### Core Modules

**`run_scraper.py`** — Main entry point. Iterates through all teams in `TEAMS`, calls `analyze_team()` for each, aggregates results, writes CSV/TSV with friendly column headers.

**`team_analysis.py`** — Core team processing logic. For each team:
- Fetches and parses roster HTML
- Normalizes player data (name, position, class, height)
- Determines positional flags (setter, pin hitter, middle blocker, defensive specialist)
- Counts returning vs. graduating vs. transferring players
- Matches incoming players from `incoming_players.py`
- Fetches stats and coach data
- Returns list of player dicts with all fields

**`roster.py`** — HTML parsing for rosters. Supports multiple layouts:
- SIDEARM card-based rosters
- SIDEARM table-based rosters
- Presto Sports format
- Fallback heuristic parsing

**`stats.py`** — Parses player statistics from HTML tables using pandas. Handles SIDEARM NextGen offensive/defensive stat tables and generic table formats. Normalizes column names (e.g., `K` → `kills`, `A` → `assists`).

**`coaches.py`** — Extracts coaching staff info (name, title, email, phone). Looks for dedicated coaching staff pages or parses from roster pages.

**`transfers.py`** — Matches players against transfer lists (`OUTGOING_TRANSFERS` and `INCOMING_PLAYERS`) to flag incoming/outgoing transfers.

**`incoming_players.py`** — Large hardcoded list of incoming players (freshmen and transfers) with their destination schools and positions. Parsed from raw text block.

**`rpi_lookup.py`** — Fetches RPI rankings and overall records from external source, builds lookup by normalized school name.

**`settings/`** — Configuration directory containing:
- `teams.py` — Master list of D1 teams with roster URLs, stats URLs, and conference affiliations
- `transfers_config.py` — Hardcoded list of outgoing transfers
- `rpi_team_name_aliases.py` — Maps official team names to RPI names when they differ (e.g., "University at Albany" → "Albany")
- `incoming_players_data.py` — Raw text data of incoming players (freshmen and transfers) by conference

**`team_pivot.py`** — Post-processing script. Reads the per-player TSV, aggregates by team, calculates:
- Position counts (returning/incoming/projected for 2026)
- Average heights by position
- Transfer lists
- Top performers (kills, assists, digs)

**`utils.py`** — Shared utilities:
- Text normalization (`normalize_text`, `normalize_player_name`)
- School name normalization for matching (`normalize_school_key`)
- Height parsing (`normalize_height`)
- Class year normalization (`normalize_class`, `class_next_year`, `is_graduating`)
- Position code extraction (`extract_position_codes`: S, OH, RS, MB, DS)
- Excel protection helpers (`excel_protect_record`, `excel_protect_phone`, `excel_unprotect`)

**`logging_utils.py`** — Centralized logging setup. Logs to console and `exports/scraper.log`.

**`labels.py`** — Formatting helpers for player labels in output (e.g., "Jane Doe (So)" for returning players).

**`export_transfers.py`** — Utility to export `OUTGOING_TRANSFERS` to CSV.

### Key Design Patterns

**Position Normalization**: Raw position strings are mapped to a standard set of codes: `S` (Setter), `OH` (Outside Hitter), `RS` (Right Side/Opposite), `MB` (Middle Blocker), `DS` (Defensive Specialist/Libero). Players can have multiple position codes (e.g., "OH/RS").

**School Name Normalization**: School names are normalized by lowercasing, stripping punctuation, and removing common words ("University", "College", "of", "the"). This enables fuzzy matching across different data sources (roster URLs, RPI data, transfer lists).

**Class Year Progression**: Class years are normalized to: `Fr`, `So`, `Jr`, `Sr`, `R-Fr`, `R-So`, `R-Jr`, `R-Sr`, `Gr`, `Fifth`. The scraper calculates next year's class to determine 2026 roster composition.

**Excel Protection**: Fields like height (`6-2`) and phone numbers are wrapped in `="value"` format in CSV output to prevent Excel from auto-converting them to dates/numbers. TSV output contains raw values.

**Roster Parsing Hierarchy**: The roster parser tries multiple strategies in sequence:
1. SIDEARM card layout
2. SIDEARM table layout
3. Presto Sports format
4. Generic heuristic parsing

**Stats Joining**: Player stats are joined to roster data by canonicalizing names (lowercase, strip punctuation, sort tokens) to handle minor variations.

### Important Data Structures

**Player dict** (from `team_analysis.py`):
- Core fields: `name`, `position`, `class`, `height`, `team`, `conference`
- Boolean flags: `is_setter`, `is_pin_hitter`, `is_middle_blocker`, `is_def_specialist`, `is_graduating`, `is_outgoing_transfer`, `is_incoming_transfer`
- Stats fields: `kills`, `assists`, `digs`, `hitting_pct`, `blocks_per_set`, etc.
- Projected 2026 counts: `returning_setter_count_2026`, `incoming_setter_count_2026`, `projected_setter_count_2026` (same for pins, middles, defs)
- Projected 2026 name lists: `returning_setter_names_2026`, `incoming_setter_names_2026`, etc.
- Coach fields: `coach1_name`, `coach1_title`, `coach1_email`, `coach1_phone`, etc. (up to coach5)

**TEAMS list** (in `teams.py`): Each entry has:
- `team`: Official school name
- `conference`: Conference name
- `url`: Roster page URL
- `stats_url`: Statistics page URL

### Roster HTML Parsing Quirks

- **SIDEARM**: Most common platform. Look for classes like `.sidearm-roster-player`, `.sidearm-roster-card`. Stats tables use `offensiveStats` and `defensiveStats` classes.
- **Presto Sports**: Uses `<rosterspot>` custom tags.
- **Staff vs. Player Detection**: The parser skips coaching staff blocks by looking for keywords like "coaching staff" or "head coach" in heading text.
- **Multi-column Stats Tables**: Stats tables sometimes use multi-level column headers. The `column_key()` function in `stats.py` flattens these.

### Data Cleaning Notes

- **Player Names**: Jersey numbers are stripped; "Last, First" format is flipped to "First Last".
- **Height**: Supports formats like `6-2`, `6'2`, `6′2″`. Converted to `F-I` format (e.g., `6-2`).
- **Class Years**: Handles variations like "Fr", "Freshman", "R-Fr", "Redshirt Freshman", "5th", "Gr".
- **Position Codes**: Raw positions like "S/DS" are split into multiple codes. Special rule: "S/DS" counts as DS, not setter (defensive specialists who can set).

### Transfer and Incoming Player Matching

Transfers and incoming players are matched by:
1. Normalizing player name (lowercase, strip punctuation)
2. Normalizing school name using `normalize_school_key()`
3. For transfers: match name + old_team (outgoing) or name + new_team (incoming)
4. For incoming players: match name + destination school

Incoming players are hardcoded in `incoming_players.py` (parsed from a raw text block with conference headers). Update this file to add new incoming players.

### Configuration Updates

**Adding a new team**: Add an entry to `TEAMS` list in `settings/teams.py` with team name, conference, roster URL, and stats URL.

**Adding incoming players**: Edit the `RAW_INCOMING_TEXT` block in `settings/incoming_players_data.py`. Format:
```
Conference Name:
Player Name - School Name - Position (Club)
```

**Adding outgoing transfers**: Edit `OUTGOING_TRANSFERS` list in `settings/transfers_config.py`. Format:
```python
{"name": "Player Name", "old_team": "Old School", "new_team": "New School"}
```

**RPI name mismatches**: If a team's official name doesn't match the RPI listing, add an alias to `RPI_TEAM_NAME_ALIASES` in `settings/rpi_team_name_aliases.py`.

## Dependencies

- **Python 3.13** (configured in venv)
- **pandas** — DataFrame operations, HTML table parsing
- **requests** — HTTP requests
- **beautifulsoup4** — HTML parsing

## Logging

Logging is configured in `logging_utils.py`. Default level is `INFO`. Logs go to both console and `exports/scraper.log`. Change level to `logging.DEBUG` in `run_scraper.py` for verbose output.
