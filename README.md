# Division 1 Women's Volleyball Scraper

A comprehensive web scraper for NCAA Division 1 Women's Volleyball programs. Collects roster data, player statistics, coach information, incoming transfers, and RPI rankings from 347 D1 volleyball team websites, then aggregates them into CSV exports for analysis.

## Features

- **Roster Scraping**: Parses player names, positions, class years, and heights from diverse website formats
- **Statistics Collection**: Gathers offensive and defensive stats (kills, assists, digs, blocks, etc.)
- **Coach Information**: Extracts coaching staff names, titles, emails, and phone numbers (~85% email capture rate)
- **Transfer Tracking**: Matches incoming and outgoing transfers across teams
- **RPI Integration**: Fetches NCAA RPI rankings and overall records
- **Team Analysis**: Projects rosters by position, calculates average heights, determines offense type (5-1 vs 6-2)
- **Robust Parsing**: Supports multiple website platforms (SIDEARM, WMT, Presto Sports, custom layouts)
- **Year-Based URLs**: Automatically appends season year to roster/stats URLs (Aug 1 - Jul 31 cycles)
- **Year-Based Data**: Manages incoming players data by season with automatic date-based selection

## Quick Start

### Prerequisites

- Python 3.13+
- Virtual environment (recommended)

### Installation

```bash
# Clone repository
git clone git@github.com:boblablaw/vb_scraper.git
cd vb_scraper

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```bash
# Run main scraper (all 347 teams, current season auto-selected)
python -m src.run_scraper

# Scrape specific season year
python -m src.run_scraper --year 2024

# Filter to specific teams
python -m src.run_scraper --team "Stanford University" --team "Nebraska University"

# Generate team-level analysis
python -m src.create_team_pivot_csv

# Export incoming players data
python scripts/export_incoming_players.py --year 2025

# Validate data quality
python validation/validate_data.py
# Report is written to validation/reports/validation_report_<timestamp>.md
```

## Project Structure

```
vb_scraper/
├── src/                              # Main executables
│   ├── run_scraper.py                # Main scraper orchestrator
│   ├── create_team_pivot_csv.py      # Team-level analysis
│   ├── create_transfers_csv.py       # Transfer data export
│   ├── merge_manual_rosters.py       # Manual roster merge utility
│   └── merge_manual_stats.py         # Manual stats merge utility
├── scraper/                          # Core scraping modules
│   ├── roster.py, stats.py, team_analysis.py, coaches.py, transfers.py, rpi_lookup.py, utils.py, logging_utils.py, incoming_players.py
├── settings/                         # Data files (JSON/text) + readmes
│   ├── teams.json                    # 347-team master list
│   ├── transfers.json                # Outgoing transfers
│   ├── rpi_team_name_aliases.json    # RPI display aliases
│   ├── incoming_players_YYYY.txt     # Year-specific incoming text (2025/26/27…)
│   ├── manual_rosters.csv, MANUAL_ROSTERS_README.md, INCOMING_PLAYERS_README.md
├── scripts/                          # Utility/ops scripts + loaders
│   ├── teams_loader.py, transfers_loader.py, rpi_aliases_loader.py, teams_urls.py
│   ├── incoming_players_data.py      # Date-based selector for incoming text files
│   ├── run_full_pipeline.py, validate_exports.py, export_incoming_players.py, parse_ncaa_pdf_stats.py
│   ├── download_sidearm_pdfs.py, fetch_coaches.py, snapshot_html.py, find_vb_stats_pdfs.py
│   ├── compare_export_to_teams.py, summarize_vb_pdfs_coverage.py, browser_automation_poc.py
├── validation/                       # Data validation
│   ├── validate_data.py
│   └── reports/                      # Generated validation_report_<timestamp>.md
├── exports/                          # Generated CSVs/logs
├── stats/                            # Source stats CSV/PDFs
├── docs/                             # Project documentation
├── tests/                            # Test suite
├── fixtures/, tempfiles/             # Stored fixtures / scratch data
└── config/                           # Local configuration (gitignored)
```

## Output Files

All outputs are written to `exports/`:

- **`d1_rosters_2025_with_stats_and_incoming.csv`** — Per-player data with stats (Team, Conference, Rank, Record, Name, Position, Class, Height, plus 24 stat columns)
- **`d1_team_pivot_2025.csv`** — Team-level aggregations with positional analysis, transfers, coaches, and projected rosters
- **`outgoing_transfers.csv`** — Transfer data export
- **`scraper.log`** — Detailed execution log
- **Validation reports** — Written to `validation/reports/validation_report_<timestamp>.md`
- **Missing teams** — Written to `validation/reports/missing_teams_<timestamp>.txt`
- **Problem teams** — Written to `validation/reports/problem_teams_<timestamp>.txt`

## Architecture

The scraper follows a clean separation of concerns:

1. **Data Collection** (`src/run_scraper.py` + `scraper/`) - Collects raw roster and stats data
2. **Analysis** (`src/create_team_pivot_csv.py`) - Performs all analytical work (projections, transfers, coaches)

### Supported Website Platforms

- **SIDEARM NextGen** - Most common platform (card and table layouts)
- **WMT Platform** - Reference-based JSON parsing (13 teams including Stanford, Auburn, Penn State)
- **Presto Sports** - Custom tag-based rosters
- **Generic HTML** - Fallback heuristic parsing for custom sites

### Data Normalization

- **Positions**: Standardized to S, OH, RS, MB, DS codes
- **Class Years**: Normalized to Fr, So, Jr, Sr, R-Fr, R-So, R-Jr, R-Sr, Gr, Fifth
- **Heights**: Converted to F-I format (e.g., 6-2)
- **School Names**: Fuzzy matching for cross-referencing (RPI, transfers, incoming players)

## Key Features

### Roster Parsing
- Handles 15+ different HTML layouts
- Strips jersey numbers, flips "Last, First" to "First Last"
- Filters out coaching staff and non-players
- Cleans position strings (removes embedded heights)
- Detects and removes club team names from class field

### Statistics Collection
- Merges offensive and defensive stat tables
- Normalizes column names across platforms
- Calculates derived stats (D/S, Rec%) when not provided
- Handles multi-level column headers

### Coach Scraping
- Finds dedicated coaching staff pages or tries common URL patterns
- Extracts names, titles, emails, phone numbers
- Achieves ~85% email capture rate across all teams

### Transfer & Incoming Player Matching
- Matches players against transfer lists by normalized name + school
- Distinguishes incoming vs outgoing transfers
- Identifies incoming freshmen and transfers by position

## Documentation

- **[WARP.md](WARP.md)** - Comprehensive technical documentation for AI assistants
- **[docs/GIT_SETUP.md](docs/GIT_SETUP.md)** - Git setup and workflow guide
- **[docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)** - High-level project overview
- **[docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)** - Current limitations and challenges
- **[docs/FUTURE_ENHANCEMENTS.md](docs/FUTURE_ENHANCEMENTS.md)** - Planned improvements
- **[docs/TEST_README.md](docs/TEST_README.md)** - Testing documentation
- **[settings/INCOMING_PLAYERS_README.md](settings/INCOMING_PLAYERS_README.md)** - Incoming players data management

## Testing

```bash
# Run test suite
python -m tests.test_settings
```

The test suite verifies:
- Settings package imports and configuration integrity
- Module dependencies and import chains
- Data consistency (unique team names, valid URLs)

All tests are designed to work with or without optional dependencies.

## Configuration (data files)

- **Teams**: `settings/teams.json` (fields: team, conference, url, stats_url)
- **Transfers**: `settings/transfers.json` (fields: name, old_team, new_team)
- **RPI aliases**: `settings/rpi_team_name_aliases.json`
- **Incoming players**: `settings/incoming_players_YYYY.txt` (conference headers + `Name - School - Position (Club)`)

Loaders in `scripts/` read these JSON/text files; `settings/__init__.py` re-exports `TEAMS`, `OUTGOING_TRANSFERS`, `RPI_TEAM_NAME_ALIASES`, and `RAW_INCOMING_TEXT` for backward compatibility. The incoming players selector in `scripts/incoming_players_data.py` chooses the correct year automatically (Aug 1–Jul 31 logic). See `settings/INCOMING_PLAYERS_README.md` for format details.

### Manual Rosters

For JavaScript-rendered sites that can't be scraped, add data to `settings/manual_rosters.csv` and run:
```bash
python -m src.merge_manual_rosters
```

### Manual Stats from NCAA PDF Box Scores

Some teams only publish stats as NCAA "Combined Team Statistics" PDFs (Livestats).
You can convert these PDFs into stats CSVs and merge them into the main export:

```bash
# 1) Place PDFs under stats/pdfs/
#    Example: stats/pdfs/university_of_kentucky_stats.pdf

# 2) Parse PDFs into SIDEARM-style stats CSVs
python scripts/parse_ncaa_pdf_stats.py

# 3) Merge manual stats into the main export
python -m src.merge_manual_stats
```

## Known Limitations

- **JavaScript-rendered rosters**: Some sites require manual data entry
- **WMT platform stats**: Served via `api.wmt.games` (e.g., `/api/statistics/teams/<id>/players`)
- **Stats availability**: Not all teams publish online statistics
- **Platform changes**: Website redesigns may break parsers
- **Rate limiting**: No delays between requests (use responsibly)

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for details.

## Data Validation

```bash
python validation/validate_data.py
```

Validates:
- Missing or invalid field values
- Failed normalization attempts
- Suspected non-player entries (staff, coaches)
- Duplicate players
- Teams with data quality issues

Reports are written to `validation/reports/`.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature-name`)
3. Make your changes
4. Run tests (`python -m tests.test_settings`)
5. Commit with clear messages
6. Push and open a Pull Request

See [docs/GIT_SETUP.md](docs/GIT_SETUP.md) for Git workflow details.

## License

This project is for educational and research purposes. Please respect website terms of service and rate limits when scraping.

## Acknowledgments

- Data sourced from NCAA Division 1 Women's Volleyball team websites
- RPI data from NCAA official rankings
- Built with pandas, requests, and BeautifulSoup4

## Contact

Issues and questions: [GitHub Issues](https://github.com/boblablaw/vb_scraper/issues)

---

**Last Updated**: December 2024  
**Python Version**: 3.13+  
**Teams Covered**: 347 NCAA D1 Women's Volleyball Programs
