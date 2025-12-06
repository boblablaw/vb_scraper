# Division 1 Women's Volleyball Scraper

Scraper + exports for NCAA Division 1 Women’s Volleyball. It pulls rosters, stats, coaches, transfers, and supporting metadata for every team in `settings/teams.json`, writes CSVs to `exports/`, and can hydrate a SQLite database for the FastAPI backend.

## What it does
- **Rosters**: Name, position, class, height, jersey, hometown, high school, photo filename.
- **Stats**: Offensive + defensive tables merged on player. Supports SIDEARM (with Playwright for dropdown defensive tables) and WMT (`api.wmt.games` or `wmt.games` stats pages).
- **Coaches**: Names, titles, emails, phone numbers (where present).
- **Transfers & incoming**: Outgoing transfers, year-based incoming lists.
- **Metadata**: RPI, airports, College Scorecard fields, team aliases.
- **Photos**: Downloads headshots to `player_photos/` (normalizes Sidearm crop URLs).
- **Bios**: Currently disabled (bio column left blank while site variability is reworked).

## Quick start

### Setup
```bash
git clone git@github.com:boblablaw/vb_scraper.git
cd vb_scraper
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run the scraper
```bash
# All teams, current season auto-selected (Aug 1–Jul 31 logic)
python -m src.run_scraper

# Specific season
python -m src.run_scraper --year 2024

# Filter teams
python -m src.run_scraper --team "Stanford University" --team "Nebraska University"

# Custom output filename
python -m src.run_scraper --output exports/my_run.csv
```

### Playwright controls
Playwright is used for SIDEARM dropdown stats and optional profile enrichment.
- `VB_DISABLE_PLAYWRIGHT=1` — skip Playwright entirely.
- `VB_PLAYWRIGHT_PROFILE_FETCH_TIMEOUT_MS` — navigation timeout (default 30000).
- `VB_PLAYWRIGHT_PROFILE_FETCH_LIMIT` — cap number of profile renders.

### Database + API (optional)
```bash
# Build SQLite (writes to data/vb.db by default)
python scripts/build_database.py --season 2025 --drop-season

# Run FastAPI (set VB_DB_URL to override; the legacy vb.db at repo root is unused)
uvicorn backend.main:app --reload
```
API endpoints: `/health`, `/conferences`, `/teams`, `/teams/{id}`, `/players`, `/players/{id}`, `/airports`, `/scorecard/{unitid}`.

### Frontend (Next.js)
```bash
cd frontend
npm install
cp .env.example .env.local   # set API URL/season
npm run dev   # http://localhost:3000
npm run lint
```

### Other CLI helpers
```bash
# Team-level analysis
python -m src.create_team_pivot_csv

# Export incoming players
python scripts/export_incoming_players.py --year 2025

# Manual stats merge (e.g., parsed NCAA PDFs in stats/)
python -m src.merge_manual_stats

# Validation
python validation/validate_data.py
```

## Key outputs (exports/)
- `d1_rosters_<year>_with_stats_and_incoming.csv` — per-player data + stats + transfers.
- `d1_team_pivot_<year>.csv` — team-level aggregations (positions, transfers, coaches).
- `outgoing_transfers.csv` — transfer export.
- `scraper.log` — run log.
- `validation/reports/*.md` — validation summaries; missing/problem team txt files.

## Project structure (high level)
```
vb_scraper/
├── src/               # Entrypoints (run_scraper, create_team_pivot_csv, merge_manual_stats, etc.)
├── scraper/           # Core logic (roster, stats, team_analysis, coaches, transfers, rpi_lookup, utils)
├── settings/          # Team list, transfers, incoming players, manual roster helpers
├── scripts/           # ETL/database + utilities (build_database.py, export_incoming_players.py, validation)
├── backend/           # FastAPI app (uses data/vb.db by default)
├── frontend/          # Next.js client
├── validation/        # Validators + generated reports
├── exports/           # Generated CSVs/logs
├── player_photos/     # Downloaded headshots
├── stats/             # Manual stats sources (CSV/PDF) for merge_manual_stats.py
└── docs/              # Additional docs
```

## Data flow (scraper)
1. `src/run_scraper.py` orchestrates seasons/teams, loads `settings/teams.json`.
2. `scraper/team_analysis.py` fetches roster HTML, delegates to parsers in `scraper/roster.py`.
3. `scraper/stats.py` builds stats lookup (SIDEARM tables + WMT API/stats pages; Playwright for SIDEARM dropdowns).
4. Roster rows + stats merged → `exports/d1_rosters_<year>_with_stats_and_incoming.csv`.
5. `src/create_team_pivot_csv.py` builds team-level pivot.

## Platforms supported
- **SIDEARM NextGen**: card/table/s-person-details; Playwright for offensive/defensive dropdowns.
- **WMT**: reference-based JSON rosters; stats via `api.wmt.games` or `wmt.games/.../season/<id>`.
- **Presto Sports**: custom tag-based parsing.
- **Generic HTML**: heuristic fallback.

## Normalization
- Positions → `S, OH, RS, MB, DS`.
- Class → `Fr, So, Jr, Sr, R-Fr, R-So, R-Jr, R-Sr, Gr, Fifth`.
- Heights → `F-I` (e.g., `6-2`).
- School names normalized for transfers/RPI matching.

## Notes / current limitations
- Bios are intentionally blank (disabled until the logic is reworked for consistency).
- Some platforms still require manual stats (use `scripts/parse_ncaa_pdf_stats.py` + `merge_manual_stats`).
- Playwright is optional but required for SIDEARM dropdown defensive stats and some profile photos.

## Documentation
- `docs/PROJECT_SUMMARY.md` — overview.
- `docs/KNOWN_LIMITATIONS.md`, `docs/FUTURE_ENHANCEMENTS.md` — caveats/roadmap.
- `docs/system_plan.md` — ETL/API/frontend plan.
- `settings/INCOMING_PLAYERS_README.md`, `settings/MANUAL_ROSTERS_README.md` — data formats.

## Testing
```bash
python -m tests.test_settings
```

## License
Educational/research use. Respect site terms and rate limits when scraping.
