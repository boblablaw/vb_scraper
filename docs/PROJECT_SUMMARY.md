# Volleyball Scraper - Project Summary

## Overview
Scraper + exports for NCAA D1 Women’s Volleyball. Collects rosters, stats, coaches, transfers, incoming players, and school metadata from the teams defined in `settings/teams.json`. Outputs CSVs in `exports/` and can hydrate a SQLite DB for the FastAPI backend.

## Current status
- Roster coverage spans SIDEARM, WMT, Presto, and custom layouts (fallback parsers included).
- WMT stats are pulled directly from `api.wmt.games`; SIDEARM dropdown stats use Playwright.
- Player bios are currently disabled (bio column blank) while being reworked.
- Photos download to `player_photos/` with Sidearm crop URL normalization.

## Quick start
```bash
source venv/bin/activate

# Full scrape (current season auto-detected)
python -m src.run_scraper

# Specific season / teams
python -m src.run_scraper --year 2025 --team "Stanford University"

# Team-level pivot
python -m src.create_team_pivot_csv

# Validation
python validation/validate_data.py
```

## Outputs (exports/)
- `d1_rosters_<year>_with_stats_and_incoming.csv` / `.tsv` — per-player data with stats + transfers.
- `d1_team_pivot_<year>.csv` — team-level aggregations (positions, transfers, coaches).
- `outgoing_transfers.csv` — transfer export.
- `scraper.log` — execution log.
- `validation/reports/*.md` — validation output; missing/problem team txt files.

## Architecture (scraper)
```
settings/teams.json → src/run_scraper.py
                          ↓
                   scraper/team_analysis.py
          roster.py (layout parsers)   stats.py (SIDEARM + WMT)
                          ↓
         exports/d1_rosters_<year>_with_stats_and_incoming.csv
                          ↓
         src/create_team_pivot_csv.py → exports/d1_team_pivot_<year>.csv
```

### Core parsers (roster.py)
1) SIDEARM card layout  
2) SIDEARM roster-list-item layout  
3) SIDEARM s-person-details layout  
4) SIDEARM table layout  
5) WMT reference-based JSON layout  
6) Drupal Views tables  
7) Embedded JSON/JavaScript arrays  
8) Generic table fallback  

## Known limitations (snapshot)
- Some JavaScript-rendered sites still need manual stats or fixtures.
- Bios are disabled until the logic is stabilized across platforms.
- A few sites may require new parsers; see `docs/KNOWN_LIMITATIONS.md` for specifics.

## Incoming/manual data
- Incoming players: `settings/incoming_players_YYYY.txt` (see `settings/INCOMING_PLAYERS_README.md`).
- Manual rosters: `settings/manual_rosters.csv` + `python -m src.merge_manual_rosters`.
- Manual stats: place parsed NCAA PDFs under `stats/` and run `python -m src.merge_manual_stats`.

## Future roadmap
Tracked in `docs/FUTURE_ENHANCEMENTS.md`.
