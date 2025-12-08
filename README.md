# VB Scraper, API, and Report Builder

Collect NCAA women's volleyball data, normalize it, and surface it through a FastAPI backend, Next.js frontend, and a PDF “Ultimate School Guide” builder.

## What’s inside
- `scripts/` — one-off utilities to scrape, merge, and enrich NCAA data (e.g., merge rosters+stats, build team pivot, fetch coaches, download logos/photos).
- `settings/` — canonical data (teams.json, transfers.json, incoming players text) read by scripts, backend, and report builder.
- `exports/` — generated CSVs: `ncaa_wvb_merged_2025.csv`, `team_pivot.csv`, caches (logo/RPI), outgoing transfers, etc.
- `assets/` — downloaded assets such as NCAA logos, player photos, and coach photos.
- `backend/` — FastAPI app exposing team/airport/scorecard/conference/player endpoints on top of the SQLite database (`data/vb.db`).
- `frontend/` — Next.js app for browsing teams and reports.
- `report_builder/` — PDF generator that combines `team_pivot.csv`, `ncaa_wvb_merged_2025.csv`, and team metadata into the Ultimate School Guide.

## Data pipeline (quick view)
1. **Merge NCAA rosters + stats** → `exports/ncaa_wvb_merged_2025.csv`  
   `python -m scripts.merge_ncaa_wvb_stats_and_rosters --stats exports/ncaa_wvb_player_stats_d1_2025.csv --rosters exports/ncaa_wvb_rosters_d1_2025.csv --output exports/ncaa_wvb_merged_2025.csv`
2. **Team pivot + RPI/enrichment** → `exports/team_pivot.csv`  
   `python -m scripts.create_team_pivot --input exports/ncaa_wvb_merged_2025.csv`
3. **(Optional) Build database** → `data/vb.db`  
   `python -m scripts.build_database --teams settings/teams.json --db data/vb.db`
4. **Generate PDF guide** → `report_builder/exports/Ultimate_School_Guide_*.pdf`  
   `python -m report_builder.cli --team-pivot exports/team_pivot.csv --rosters exports/ncaa_wvb_merged_2025.csv`

## Getting started
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Regenerate data
- Merge NCAA data: see step 1 above.
- Rebuild team pivot: step 2 above.
- Refresh coaches (with photo download): `python -m scripts.fetch_coaches`

### Run the API
```bash
uvicorn backend.main:app --reload
# API docs at http://localhost:8000/docs
```

### Run the frontend
```bash
cd frontend
npm install
npm run dev
```

### Build the PDF guide
```bash
python -m report_builder.cli \
  --team-pivot exports/team_pivot.csv \
  --rosters exports/ncaa_wvb_merged_2025.csv
```

## Key data files and columns
- `exports/ncaa_wvb_merged_2025.csv` — merged roster/stats with columns like `School`, `Team`, `Conference`, `Player`, `Yr`, `Pos`, `Ht`, `Assists`, `Digs`, `Kills`. Used by team pivot and report builder.
- `exports/team_pivot.csv` — team-level aggregates: RPI rank/record, offense type, returning/incoming position counts, transfer summaries, coach columns.
- `settings/teams.json` — canonical team metadata (urls, aliases, airports, politics label, niche data, logos, coaches).
- `settings/transfers.json` — outgoing transfer list.
- `settings/incoming_players_*.txt` — freeform incoming/commit text parsed by scripts.

## Notes
- Network access is required for scraping RPI pages, logos, coaches pages, and downloading photos.
- Many scripts cache results under `exports/` (e.g., RPI lookup cache) to reduce network traffic.
- The `scripts/helpers` package houses shared loaders, parsers, and logging utilities used across scripts and the settings package.
