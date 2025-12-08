# Application Overview (Backend, Frontend, Data)

This project bundles data collection scripts, a FastAPI backend, a Next.js frontend, and a PDF builder driven by shared settings and exports.

## Architecture at a glance
- **Data layer**: canonical metadata in `settings/teams.json`, transfers in `settings/transfers.json`, incoming players text files, generated CSVs in `exports/`, and SQLite DB at `data/vb.db`.
- **Backend**: FastAPI app (`backend/main.py`) with routers for health, conferences, airports, teams, players, and scorecard data. Uses `backend/app/database.py` to talk to the SQLite DB (built via `scripts/build_database.py`).
- **Frontend**: Next.js app under `frontend/` that consumes the API and renders team pages.
- **Report builder**: lives in `report_builder/`, producing PDFs from `team_pivot.csv`, `ncaa_wvb_merged_2025.csv`, and team metadata.
- **Shared helpers**: `scripts/helpers/` contains loaders, parsers, logging, RPI lookup, and utility functions shared by scripts and settings.

## Data model (key sources)
- `settings/teams.json`: team name, conference, URLs, aliases, airport info, politics label, niche data, risk watchouts, logos, coaches (with optional `coach_photo`), and NCAA IDs.
- `settings/transfers.json`: outgoing transfers with `name`, `old_team`, `new_team`.
- `settings/incoming_players_*.txt`: season-specific freeform text parsed into incoming/commit lists.
- `exports/ncaa_wvb_merged_2025.csv`: merged roster + stats (columns: School/Team, Player/Name, Yr, Pos, Ht, Kills, Assists, Digs, etc.).
- `exports/team_pivot.csv`: team-level aggregation with RPI rank/record, offense type, returning/incoming position counts, transfer summaries, and coach columns.
- `data/vb.db`: SQLite database populated from settings/exports for API consumption.

### SQLite schema (vb.db)
- **teams**: id (PK), name, short_name, conference_id (FK -> conferences), city/state, url, stats_url, tier, political_label, lat/lon, airport_* fields, aliases_json, niche_json, notes, risk_watchouts, scorecard_unitid/metadata, coaches_json, logo_filename, timestamps.
- **conferences**: id (PK), name.
- **coaches**: id (PK), team_id (FK -> teams), name, title, email, phone, sort_order, timestamps.
- **players**: id (PK), team_id (FK -> teams), name, position, class_year, height_inches, season.
- **player_stats**: composite PK (player_id, season), plus per-set/aggregate stats (kills, assists, digs, blocks, serving, hitting, etc.).
- **airports**: id (PK), ident/iata/local codes, name, lat/lon, region, score, last_updated.
- **scorecard_schools**: unitid (PK) + Scorecard fields (admission rate, tuition in/out, cost, grad rate, retention, Pell %, earnings, etc.).
- **ingestion_runs**: id (PK), started_at/finished_at, season, source file paths, notes (tracks ETL runs).

## Data pipeline
1. **Scrape/download** NCAA rosters and stats (saved under `exports/`).
2. **Merge rosters + stats** into `exports/ncaa_wvb_merged_2025.csv` (`python -m scripts.merge_ncaa_wvb_stats_and_rosters ...`).
3. **Enrich team pivot** with RPI, transfers, incoming players, coaches (`python -m scripts.create_team_pivot` → `exports/team_pivot.csv`).
4. **(Optional) Build DB** for the API (`python -m scripts.build_database --db data/vb.db`).
5. **Serve** via FastAPI (`uvicorn backend.main:app --reload`) and the Next.js frontend (`npm run dev` from `frontend/`).
6. **Generate PDF** with the report builder (`python -m report_builder.cli`).

## Backend notes
- Entry: `backend/main.py`; routers live in `backend/app/routers/`.
- Config: `backend/app/config.py` sets API metadata; dependencies manage DB sessions.
- Expected data: `data/vb.db` populated by `scripts/build_database.py` using `settings/teams.json` and exports.

## Frontend notes
- Located in `frontend/`, built with Next.js/TypeScript.
- Uses API endpoints for teams and scorecard data; pages live under `frontend/src/app/teams/...`.
- Run locally with `npm install && npm run dev`.

## Maintenance tips
- Treat `settings/teams.json` as the single source of truth for team metadata and aliases.
- Keep CSV exports up to date before building pivots, database, or PDF outputs.
- Shared code belongs in `scripts/helpers` to avoid drift between scripts and settings.
