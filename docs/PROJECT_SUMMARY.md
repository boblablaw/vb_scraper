# Volleyball Scraper - Project Summary

## Overview
Web scraper for Division 1 Women's Volleyball programs. Collects roster data, player statistics, coach information, incoming transfers, and RPI rankings from 347 NCAA D1 volleyball team websites.

## Current Status (as of 2025-11-29)

### Coverage
- **305 of 347 teams (87.9%)**
- **8,356+ player records**
- **296 teams** with complete roster data
- **9 teams** recovered today through URL fixes and parser enhancements

### What's Working
✅ Automatic roster scraping from 305 D1 programs  
✅ Player data: name, position, class, height, stats  
✅ Coach contact information (when available)  
✅ Transfer tracking (incoming/outgoing)  
✅ RPI rankings integration  
✅ CSV/TSV export with Excel-friendly formatting  
✅ Team-level pivot tables and aggregations  

### Recent Improvements (2025-11-29)
- Fixed 9 team URLs (DNS errors, domain changes, 404s)
- Added new SIDEARM s-person-details parser (+44 players from Marshall)
- Created data validation tooling (`scripts/validate_exports.py`)
- Built team coverage analyzer (`scripts/compare_export_to_teams.py`)
- Added `--team` filtering for targeted scraping
- Captured 36 HTML fixtures for debugging

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Run full scraper (takes ~10-15 minutes, auto-detects year)
python -m src.run_scraper

# Optional: Specify year explicitly
python -m src.run_scraper --year 2025

# Generate team-level pivot table
python -m src.create_team_pivot_csv

# Validate data quality
python validation/validate_data.py
```

## Outputs

All files written to `exports/`:
- `d1_rosters_2026_with_stats_and_incoming.csv` - Per-player data (Excel-friendly)
- `d1_rosters_2026_with_stats_and_incoming.tsv` - Per-player data (raw)
- `d1_team_pivot_2026.csv` - Team-level aggregations
- `scraper.log` - Detailed execution log

## Architecture

```
settings/teams_urls.py (year-based URLs) → src/run_scraper.py → team_analysis.py
                                                ↓                      ↓
                                           roster.py               stats.py
                                           coaches.py              transfers.py
                                           rpi_lookup.py
                                                ↓
                                          exports/*.csv
                                                ↓
src/create_team_pivot_csv.py ← settings/incoming_players_data.py (year-based)
        ↓
exports/d1_team_pivot_2025.csv
```

**Core Parsers** (in `roster.py`):
1. SIDEARM card layout
2. SIDEARM roster-list-item layout  
3. SIDEARM s-person-details layout (NEW)
4. SIDEARM table layout
5. Heading-card (WMT) layout
6. Drupal Views tables
7. Embedded JSON/JavaScript arrays
8. Generic table fallback

## Known Limitations

### JavaScript-Rendered Sites (28 teams - 66% of failures)
Cannot scrape without browser automation:
- **12 SEC schools**: Alabama, Arkansas, Florida, Georgia, Kentucky, LSU, Missouri, Oklahoma, South Carolina, Tennessee, Texas, Vanderbilt
- **16 other schools**: WCC (7), Summit League (4), others (5)

**Why**: Sites use client-side JavaScript rendering (React/Angular/Vue)  
**Fix**: Requires Selenium/Playwright (12-16 hours effort)  
**See**: `FUTURE_ENHANCEMENTS.md` Phase 2

### Parseable HTML (7 teams - Could fix in 3-4 hours)
HTML accessible but needs custom parser:
- Pacific, Oregon State, JMU, Citadel, Utah Tech, Troy, others

**See**: `FUTURE_ENHANCEMENTS.md` Phase 1  
**Fixtures**: `fixtures/html/*.html` for analysis

### Infrastructure Issues (7 teams)
Domain problems or access restrictions:
- New Mexico (domain parking), Wyoming (empty page), Utah State (redirect)
- Central Connecticut State, Tennessee Tech (404/bot protection)

**See**: `KNOWN_LIMITATIONS.md` for details

## Tools & Scripts

### Data Quality
```bash
# Run validation
python validation/validate_data.py

# Output: validation/reports/validation_report_*.md
#         validation/reports/problem_teams_*.txt
```

### Manual Stats from NCAA PDFs
```bash
# Convert "Combined Team Statistics" PDFs -> stats/*.csv
python scripts/parse_ncaa_pdf_stats.py

# Merge those stats into the main roster export
python -m src.merge_manual_stats
```

### Targeted Scraping
```bash
# Scrape specific teams
python -m src.run_scraper --team "University of Alabama" --team "LSU"

# Scrape with specific year
python -m src.run_scraper --year 2024 --team "Stanford University"

# Custom output filename
python -m src.run_scraper --output test_export_2025
```

### Incoming Players Management
```bash
# Export incoming players data to CSV
python scripts/export_incoming_players.py --year 2026

# List available years
python scripts/export_incoming_players.py --list

# Custom output path
python scripts/export_incoming_players.py --year 2026 --output exports/incoming_2026.csv
```

## Future Roadmap

### Phase 1: Quick Wins (3-4 hours) → 90% coverage
- Fix 7-10 parseable HTML teams
- Add 1-2 new parsers for Pacific, JMU, etc.
- **Outcome**: 312-315 teams

### Phase 2: Browser Automation (12-16 hours) → 98% coverage  
- Implement Selenium/Playwright
- Fix 28 JavaScript-rendered teams
- **Outcome**: 333-338 teams

### Phase 3: Infrastructure (1-2 hours) → Final polish
- Research domain changes
- Document permanently unavailable teams
- **Outcome**: 335-340 teams

**See**: `FUTURE_ENHANCEMENTS.md` for complete roadmap

## Testing

```bash
# Run all unit tests
python -m tests.test_settings

# Check specific team
python -m src.run_scraper --team "Marshall University"
grep "Marshall" exports/scraper.log
```

## Maintenance

### Regular Checks
```bash
# Weekly: Check for new failures
grep "No players parsed" exports/scraper.log | wc -l

# Quarterly: Full data quality audit
python validation/validate_data.py
```

### When Sites Change
1. Update URL in `settings/teams_urls.py` (base URL without year)
2. Test: `python -m src.run_scraper --team "School"`
3. Check logs: `grep "School" exports/scraper.log`

### Adding Incoming Players
1. Edit appropriate year file: `settings/incoming_players_data_YYYY.py`
2. See format in `settings/INCOMING_PLAYERS_README.md`
3. Verify: `python scripts/export_incoming_players.py --year YYYY`

## Documentation

- **WARP.md** - Complete project documentation
- **FUTURE_ENHANCEMENTS.md** - Roadmap for 90-98% coverage
- **KNOWN_LIMITATIONS.md** - Detailed breakdown of unavailable teams
- **TEST_README.md** - Testing guide
- **This file** - Project summary

## Dependencies

```bash
pip install -r requirements.txt
```

Optional (for future enhancements):
```bash
pip install selenium playwright lxml
```

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Teams | 347 |
| Successfully Scraped | 305 (87.9%) |
| Player Records | 8,356+ |
| Conferences Covered | All D1 conferences |
| JS-Rendered (blocked) | 28 teams |
| Parseable (not impl.) | 7 teams |
| Infrastructure issues | 7 teams |

## Contact & Support

For issues or questions:
1. Check `KNOWN_LIMITATIONS.md` for known issues
2. Review `FUTURE_ENHANCEMENTS.md` for roadmap
3. Run `python scripts/validate_exports.py --help`

---

**Last Updated**: 2025-11-29  
**Version**: 2.0 (Data Quality Improvements)  
**Coverage**: 305/347 teams (87.9%)
