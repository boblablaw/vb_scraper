# vb_scraper data platform plan (Dec 5, 2025)

## Goals
- Persist scraped rosters/stats plus school metadata in a queryable database.
- Refresh the database whenever new CSV/JSON drops are produced by the scraper.
- Expose a clean API for a modern frontend (search, filters, compare views, maps).

## Stack proposal
- **Database (now):** SQLite (`data/vb.db`) built locally for fast iteration.  
  **Later:** swap to Postgres by replacing the connection string in the ETL/API layers.
- **ETL:** `scripts/build_database.py` (pandas + sqlite3). Idempotent upserts keyed on team + player.
- **API:** FastAPI + SQLAlchemy/SQLModel, uvicorn. Endpoints below.
- **Frontend:** Next.js (React) with TypeScript + TanStack Query; Tailwind or shadcn UI; Map component (Mapbox GL or Leaflet) for airport proximity.

## Data model (implemented in SQLite)
- `conferences(id, name)`
- `airports(id, ident, type, name, latitude, longitude, iso_country, iso_region, municipality, iata_code, local_code, score, last_updated)`
- `scorecard_schools(unitid, instnm, city, state, adm_rate, sat_avg, tuition_in, tuition_out, cost_t4, grad_rate, retention_rate, pct_pell, pct_fulltime_fac, median_earnings)`
- `teams(id, name, short_name, conference_id, city, state, url, stats_url, tier, political_label, latitude, longitude, airport_code, airport_name, airport_drive_time, airport_notes, aliases_json, niche_json, notes, risk_watchouts, scorecard_unitid, scorecard_confidence, scorecard_match_name, created_at, updated_at)`
- `players(id, team_id, name, position, class_year, height_inches, season)`
- `player_stats(player_id, season, ms, mp, sp, pts, pts_per_set, k, k_per_set, ae, ta, hit_pct, assists, assists_per_set, sa, sa_per_set, se, digs, digs_per_set, re, tre, rec_pct, bs, ba, tb, blocks_per_set, bhe)`
- `ingestion_runs(id, started_at, finished_at, season, rosters_path, teams_path, airports_path, scorecard_path, notes)`

## ETL / refresh workflow
- Build or refresh DB for a season:
  - `python scripts/build_database.py --season 2025`
  - Add `--drop-season` to wipe existing player/stats rows for that season before loading.
  - Optional flags: `--db data/vb.db`, `--airport-types large_airport medium_airport`.
  - Note: the legacy `vb.db` in the repo root is unused; SQLite lives under `data/`.
- What it does:
  - Loads US airports (filtering to medium/large) from `external_data/airports_us.csv`.
  - Loads teams & conferences from `settings/teams.json` (keeps aliases/niche JSON, airport metadata, scorecard links).
  - Loads College Scorecard rows only for the unitids referenced by teams.
  - Upserts players + stats from `exports/rosters_and_stats.csv` for the given season.
  - Records an ingestion run summary.

## API sketch (FastAPI)
- `GET /teams` — filters: conference, state, tier, has_airport.
- `GET /teams/{id}` — includes joined airport + scorecard snippets.
- `GET /players` — filters: team_id, season, position, class_year; pagination.
- `GET /players/{id}/stats` — season filter, per-set numbers.
- `GET /airports` — filters: state, type, iata_code search.
- `GET /scorecard/{unitid}` — returns academics/value metrics.
- `POST /refresh` — trigger ETL run (invokes `build_database.py`); protect with token/auth.

## Frontend feature ideas
- **Team explorer:** cards + filters, chip list by conference/tier/political lean; quick stats (record, top performers, airport distance).
- **Roster page:** sortable table with per-set stats, class filters, position filters; trend sparklines per metric.
- **Compare teams:** side-by-side scorecard metrics + roster averages + airport convenience.
- **Map view:** plot teams with nearest airport; hover for drive time; toggle conference layers.
- **Search:** fuzzy search across team names/aliases and player names.

## Next steps to go from here
1) Decide target season(s) and run the ETL to generate `data/vb.db`.  
2) Pick backend framework (FastAPI recommended) and generate models from the existing schema.  
3) Scaffold Next.js app consuming the API; start with Teams list + Roster detail.  
4) Wire a small admin page to trigger ETL refresh (or run via cron/GitHub Actions).  
5) Add tests around ETL (row counts, duplicate handling) and API contracts.
