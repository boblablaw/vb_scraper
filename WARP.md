# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a web scraper for Division 1 Women's Volleyball programs. It collects roster data, player statistics, coach information, incoming transfers, and RPI rankings from NCAA D1 volleyball team websites, then aggregates them into CSV exports for analysis.

**Architecture:** The scraper follows a clean separation of concerns:
- **Data Collection** (`src/run_scraper.py` + `scraper/`): Collects raw roster and stats data
- **Analysis** (`src/create_team_pivot_csv.py`): Performs all analytical work (projections, transfers, coaches)

**Project Structure:**
```
vb_scraper/
├── src/                    # Main source code
│   ├── run_scraper.py
│   ├── create_team_pivot_csv.py
│   ├── create_transfers_csv.py
│   ├── merge_manual_rosters.py
│   └── merge_manual_stats.py
├── scraper/                # Core scraping modules
│   ├── roster.py
│   ├── stats.py
│   ├── team_analysis.py
│   ├── coaches.py
│   ├── transfers.py
│   ├── rpi_lookup.py
│   ├── logging_utils.py
│   └── utils.py
├── settings/               # Configuration data
│   ├── teams.py
│   ├── transfers_config.py
│   ├── rpi_team_name_aliases.py
│   ├── incoming_players_data.py
│   └── manual_rosters.csv
├── tests/                  # Test suite
│   ├── test_settings.py
│   └── test_data/
├── validation/             # Data validation tools
│   ├── validate_data.py
│   └── reports/
├── scripts/                # Utility scripts
│   └── find_missing_urls*.py
├── docs/                   # Documentation
│   ├── PROJECT_SUMMARY.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── FUTURE_ENHANCEMENTS.md
│   └── TEST_README.md
└── exports/                # Output files
```

## Common Commands

### Running the Scraper

```bash
# Activate virtual environment
source venv/bin/activate

# 1. Run the main scraper (generates per-player data with stats)
python -m src.run_scraper

# Optional: Filter to specific teams
python -m src.run_scraper --team "Brigham Young University" --team "Stanford University"

# Optional: Use custom output filename
python -m src.run_scraper --output my_custom_rosters_2025

# 2. (Optional) Merge manual roster data for JavaScript-rendered sites
python -m src.merge_manual_rosters

# 3. Generate team-level analysis and aggregations
python -m src.create_team_pivot_csv

# 4. (Optional) Export transfer data separately
python -m src.create_transfers_csv

# 5. (Optional) Validate data quality
python validation/validate_data.py
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

### Main Exports
- `d1_rosters_2025_with_stats_and_incoming.csv` — Per-player data with abbreviated stat columns (Team, Conference, Rank, Record, Name, Position, Class, Height, MS, MP, SP, PTS, PTS/S, K, K/S, AE, TA, HIT%, A, A/S, SA, SA/S, SE, D, D/S, RE, TRE, Rec%, BS, BA, TB, B/S, BHE)
- `d1_team_pivot_2025.csv` — Team-level aggregated data with positional analysis, transfers, coaches, and projected rosters
- `outgoing_transfers.csv` — Exported transfer data

### Logs & Validation
- `scraper.log` — Detailed execution log
- `validation/reports/validation_report_*.md` — Data quality validation reports
- `validation/reports/problem_teams_*.txt` — List of teams with data issues

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. SCRAPING PHASE                                                       │
└─────────────────────────────────────────────────────────────────────────┘

settings/teams.py (347 D1 teams + URLs)
    ↓
src/run_scraper.py (orchestrator)
    ├─ rpi_lookup.py (fetch RPI rankings)
    └─ For each team:
        team_analysis.py (SIMPLIFIED - data collection only)
            ├─ roster.py (parse HTML → name/position/class/height)
            │   ├─ SIDEARM card/table layouts
            │   ├─ WMT reference-based JSON
            │   ├─ Drupal Views roster
            │   ├─ Generic table fallback
            │   └─ Data cleaners (strip heights from positions, club names from class)
            ├─ stats.py (parse stats tables → all player stats)
            │   ├─ Merges offensive + defensive stats
            │   ├─ Normalizes column names
            │   └─ Calculates derived stats (D/S, Rec%)
            └─ Position/class normalization (utils.py)
    ↓
exports/d1_rosters_2025_with_stats_and_incoming.csv

┌─────────────────────────────────────────────────────────────────────────┐
│ 2. MANUAL ROSTER MERGE (optional, for JS-rendered sites)               │
└─────────────────────────────────────────────────────────────────────────┘

settings/manual_rosters.csv (manually entered data)
    ↓
src/merge_manual_rosters.py
    ├─ Load scraped CSV
    ├─ Remove teams with manual data from scraped results
    ├─ Add manual roster entries
    └─ Write merged data back to CSV
    ↓
exports/d1_rosters_2025_with_stats_and_incoming.csv (updated)

┌─────────────────────────────────────────────────────────────────────────┐
│ 3. POST-PROCESSING & EXPORTS                                            │
└─────────────────────────────────────────────────────────────────────────┘

src/create_team_pivot_csv.py (team-level analysis)
    ├─ Read scraped roster CSV
    ├─ Calculate positional flags from position codes
    ├─ Determine returning vs graduating players
    ├─ Match incoming players (from incoming_players_data.py)
    ├─ Match transfers (from OUTGOING_TRANSFERS)
    ├─ Scrape coach information (emails, phones)
    ├─ Calculate projected 2025 rosters by position
    ├─ Calculate average heights by position
    ├─ Determine offense type (5-1 vs 6-2 based on assists)
    └─ Group by team
    ↓
exports/d1_team_pivot_2025.csv

src/create_transfers_csv.py
    └─ Export settings/transfers_config.py to CSV
    ↓
exports/outgoing_transfers.csv

┌─────────────────────────────────────────────────────────────────────────┐
│ 4. VALIDATION (optional)                                                │
└─────────────────────────────────────────────────────────────────────────┘

validation/validate_data.py
    ├─ Read exports/d1_rosters_2025_with_stats_and_incoming.csv
    ├─ Check data quality (missing fields, invalid formats, normalization failures)
    ├─ Detect suspected non-players
    └─ Identify problem teams
    ↓
validation/reports/validation_report_*.md
validation/reports/problem_teams_*.txt
```

### Core Modules

**`src/run_scraper.py`** — Main entry point. Iterates through all teams in `TEAMS`, calls `analyze_team()` for each, aggregates results, writes CSV with abbreviated column headers. Also calculates derived stats (D/S, Rec%) when not provided by source.

**`scraper/team_analysis.py`** — Simplified data collection module (111 lines). For each team:
- Fetches and parses roster HTML
- Normalizes player data (name, position, class, height)
- Fetches player statistics
- Fetches RPI data
- Returns simplified player dicts with roster + stats only
- **Does NOT** perform any analysis, projections, or coach scraping

**`roster.py`** — HTML parsing for rosters. Supports multiple layouts:
- SIDEARM card-based rosters
- SIDEARM table-based rosters
- Presto Sports format
- Fallback heuristic parsing

**`stats.py`** — Parses player statistics from HTML tables using pandas. Handles SIDEARM NextGen offensive/defensive stat tables and generic table formats. Normalizes column names (e.g., `K` → `kills`, `A` → `assists`).

**`scraper/coaches.py`** — Extracts coaching staff info (name, title, email, phone). Looks for dedicated coaching staff pages or tries common URL patterns (/coaches, /staff) when no link exists. Achieves ~85% email capture rate.

**`transfers.py`** — Matches players against transfer lists (`OUTGOING_TRANSFERS` and `INCOMING_PLAYERS`) to flag incoming/outgoing transfers.

**`incoming_players.py`** — Large hardcoded list of incoming players (freshmen and transfers) with their destination schools and positions. Parsed from raw text block.

**`rpi_lookup.py`** — Fetches RPI rankings and overall records from external source, builds lookup by normalized school name.

**`settings/`** — Configuration directory containing:
- `teams.py` — Master list of D1 teams with roster URLs, stats URLs, and conference affiliations
- `transfers_config.py` — Hardcoded list of outgoing transfers
- `rpi_team_name_aliases.py` — Maps official team names to RPI names when they differ (e.g., "University at Albany" → "Albany")
- `incoming_players_data.py` — Raw text data of incoming players (freshmen and transfers) by conference
- `manual_rosters.csv` — Manually-entered roster data for JavaScript-rendered sites that can't be scraped

**`src/merge_manual_rosters.py`** — Manual roster merge script. For teams with JavaScript-rendered rosters:
- Reads manual roster data from `settings/manual_rosters.csv`
- Removes scraped data for teams with manual entries
- Adds manual roster rows with auto-detected position flags
- Writes merged data back to main export CSV

**`src/create_team_pivot_csv.py`** — Team-level analysis script (414 lines). Reads the per-player CSV, performs all analytical work:
- Calculates positional flags from position codes (S, OH, RS, MB, DS)
- Determines returning vs graduating players from class years
- Matches incoming players and transfers
- Scrapes coach information (name, title, email, phone)
- Calculates projected 2025 roster by position
- Calculates average heights by position
- Determines offense type (5-1 vs 6-2 based on assists >= 350)
- Outputs team-level summaries with all analysis

**`src/create_transfers_csv.py`** — Transfer data export utility. Exports `OUTGOING_TRANSFERS` from `settings/transfers_config.py` to CSV format

**`validation/validate_data.py`** — Data quality validation script. Analyzes scraped data for:
- Missing or invalid field values (position, height, class)
- Failed normalization (values that couldn't be mapped to standard formats)
- Suspected non-player entries (staff, coaches)
- Duplicate players
- Teams with data quality issues
- Generates validation reports and problem team lists

**`scraper/utils.py`** — Shared utilities:
- Text normalization (`normalize_text`, `normalize_player_name`)
- School name normalization for matching (`normalize_school_key`)
- Height parsing (`normalize_height`)
- Class year normalization (`normalize_class`, `class_next_year`, `is_graduating`)
- Position code extraction (`extract_position_codes`: S, OH, RS, MB, DS)
- Excel protection helpers (`excel_protect_record`, `excel_protect_phone`, `excel_unprotect`)

**`scraper/logging_utils.py`** — Centralized logging configuration. Sets up console and file logging to `exports/scraper.log`


### Key Design Patterns

**Position Normalization**: Raw position strings are mapped to a standard set of codes: `S` (Setter), `OH` (Outside Hitter), `RS` (Right Side/Opposite), `MB` (Middle Blocker), `DS` (Defensive Specialist/Libero). Players can have multiple position codes (e.g., "OH/RS").

**School Name Normalization**: School names are normalized by lowercasing, stripping punctuation, and removing common words ("University", "College", "of", "the"). This enables fuzzy matching across different data sources (roster URLs, RPI data, transfer lists).

**Class Year Progression**: Class years are normalized to: `Fr`, `So`, `Jr`, `Sr`, `R-Fr`, `R-So`, `R-Jr`, `R-Sr`, `Gr`, `Fifth`. The scraper calculates next year's class to determine 2026 roster composition.

**Excel Protection**: Fields like height (`6-2`) and phone numbers are wrapped in `="value"` format in CSV output to prevent Excel from auto-converting them to dates/numbers. TSV output contains raw values.

**Roster Parsing Hierarchy**: The roster parser tries multiple strategies in sequence:
1. SIDEARM card layout
2. SIDEARM table layout
3. Drupal Views roster
4. Heading-card layout
5. WMT reference-based JSON
6. Embedded JSON blobs
7. Number-name-details pattern
8. Presto Sports format
9. Generic heuristic table parsing

**Stats Joining**: Player stats are joined to roster data by canonicalizing names (lowercase, strip punctuation, sort tokens) to handle minor variations.

### Important Data Structures

**Player dict** (from `team_analysis.py`):
- Core fields: `team`, `conference`, `rank`, `record`, `name`, `position`, `class`, `height`
- Stats fields: All player stats with abbreviated names (MS, MP, SP, PTS, PTS/S, K, K/S, AE, TA, HIT%, A, A/S, SA, SA/S, SE, D, D/S, RE, TRE, Rec%, BS, BA, TB, B/S, BHE)
- Note: No boolean flags, no projections, no coach data in scraper output

**Team pivot dict** (from `src/create_team_pivot_csv.py`):
- Core fields: `team`, `conference`, `rank`, `record`, `roster_url`, `stats_url`
- Position analysis: `returning_setter_count`, `returning_setter_names`, `incoming_setter_count`, `incoming_setter_names`, `projected_setter_count`, `avg_setter_height` (same for pins, middles, defs)
- Transfers: `outgoing_transfers`, `incoming_transfers`
- Analysis: `offense_type`
- Coach fields: `coach1_name`, `coach1_title`, `coach1_email`, `coach1_phone`, etc. (up to coach5)

**TEAMS list** (in `teams.py`): Each entry has:
- `team`: Official school name
- `conference`: Conference name
- `url`: Roster page URL
- `stats_url`: Statistics page URL

### Roster HTML Parsing Quirks

- **SIDEARM**: Most common platform. Look for classes like `.sidearm-roster-player`, `.sidearm-roster-card`. Stats tables use `offensiveStats` and `defensiveStats` classes.
- **WMT Platform**: Uses reference-based JSON data embedded in script tags. The parser (`parse_wmt_reference_json_roster()`) extracts large JSON arrays (50KB+, 1000+ items), finds roster reference keys, and recursively resolves integer references to extract player data (names, positions, heights, class years). This parser successfully handles 13 teams including Auburn, Stanford, Virginia Tech, Arizona State, Cincinnati, UCF, Iowa, Penn State, Purdue, Bradley, SDSU, SJSU, and Old Dominion. **Note**: WMT platform stats pages are JavaScript-rendered without parseable JSON data—stats for these teams cannot be scraped without browser automation.
- **Presto Sports**: Uses `<rosterspot>` custom tags.
- **Staff vs. Player Detection**: The parser skips coaching staff blocks by looking for keywords like "coaching staff" or "head coach" in heading text.
- **Multi-column Stats Tables**: Stats tables sometimes use multi-level column headers. The `column_key()` function in `stats.py` flattens these.

### Data Cleaning Notes

- **Player Names**: Jersey numbers are stripped; "Last, First" format is flipped to "First Last".
- **Height**: Supports formats like `6-2`, `6'2`, `6′2″`. Converted to `F-I` format (e.g., `6-2`). Placeholder text like "Jersey Number" is filtered out during parsing.
- **Class Years**: Handles variations like "Fr", "Freshman", "R-Fr", "Redshirt Freshman", "5th", "6th", "Gr". Also supports "First Year" (FY/Fy/Fy.) which maps to Fr, and redshirt variants (RFr./R-Fy./Rf.) which map to R-Fr. Club volleyball team names (containing "club", "volleyball", "vbc") are filtered out if they appear in the class field.
- **Position Codes**: Raw positions like "S/DS" are split into multiple codes. Special rule: "S/DS" counts as DS, not setter (defensive specialists who can set). **MH** (Middle Hitter) is recognized as equivalent to **MB** (Middle Blocker). Height patterns embedded in position strings (e.g., "Left Side LS 5'10\"") are automatically stripped.

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

Logging is configured in `scraper/logging_utils.py`. Default level is `INFO`. Logs go to both console and `exports/scraper.log`. Change level to `logging.DEBUG` in `src/run_scraper.py` for verbose output.

## Testing

The project includes unit tests for the settings package to verify configuration integrity.

### Running Tests

```bash
# Run all tests
python -m tests.test_settings
```

### Test Coverage

The test suite (`tests/test_settings.py`) verifies:

1. **Settings Package Imports** — All configuration data (TEAMS, OUTGOING_TRANSFERS, RPI_TEAM_NAME_ALIASES, RAW_INCOMING_TEXT) is correctly imported and accessible
2. **Dependent Module Imports** — All modules can successfully import configuration data from the settings package
3. **Data Consistency** — Configuration data maintains internal consistency (unique team names, valid URLs, etc.)

Tests are designed to work with or without optional dependencies (pandas, requests, beautifulsoup4). Tests requiring missing dependencies will be automatically skipped.

See `docs/TEST_README.md` for detailed test documentation.
