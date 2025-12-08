# Report Builder Guide

The report builder generates the “Ultimate School Guide” PDF by combining NCAA roster/stats data, team pivot metrics, and metadata from `settings/teams.json`.

## Inputs
- `exports/team_pivot.csv`
  - Columns used: `team`, `conference`, `rank`, `record`, `offense_type`, projected counts and lists for setters/pins/middles/defenders, transfers, and coach columns packed by `scripts/helpers/coaches_cache.pack_coaches_for_row`.
- `exports/ncaa_wvb_merged_2025.csv`
  - Expected columns (case-insensitive): `team`/`school`, `name`/`player`, `yr`, `pos`, `ht`, `kills`, `assists`, `digs`, optional `on_2026_roster` flags.
- `settings/teams.json`
  - Core metadata: aliases, conference, airports, politics label, niche data, logos, coaches, risk watchouts.
- Optional: `settings/coaches_cache.json` (unused now that coaches live in `teams.json`, but path remains configurable).
- Config overrides: `report_builder/config/guide.yml` + defaults in `guide.defaults.yml`.
- Player config: `report_builder/config/players/*.yml` (home location, target schools, overrides).

## Running it
```bash
python -m report_builder.cli \
  --team-pivot exports/team_pivot.csv \
  --rosters exports/ncaa_wvb_merged_2025.csv \
  --output report_builder/exports/Ultimate_School_Guide.pdf
```

CLI flags:
- `--team-pivot` path to team_pivot.csv
- `--rosters` path to ncaa_wvb_merged_2025.csv
- `--logos-dir` custom logo directory (defaults to `report_builder/logos`)
- `--us-map` custom map image
- `--coaches-cache` optional cache path (kept for compatibility)
- `--player-settings` pick a different player YAML

The same paths can be overridden via `report_builder/config/guide.yml` under `paths.*`.

## Data flow inside the builder
1. Load `settings/teams.json` into `SCHOOLS`, seeding aliases, airport info, risk notes, and logo map.
2. Apply config overrides from `guide.defaults.yml` and `guide.yml` (team name aliases, risk notes, airports, politics labels, logo overrides, paths).
3. Enrich `SCHOOLS` from `team_pivot.csv` (conference, offense type, RPI rank/record, projections).
4. Attach roster snapshots from `ncaa_wvb_merged_2025.csv` (filters out graduating classes; honors optional include flags).
5. Compute travel, fit scores, rankings, and render sections to PDF.

## Expected columns (roster CSV)
The builder tolerates column casing and common variants:
- Team key: `team` or `school`
- Player name: `name`, `player`, or `player_name`
- Class: `class_2026`, `class_2025`, `class`, `yr`, `eligibility`, `year`
- Position: `position`, `pos`
- Height: `height_safe`, `height`, `height_display`, `ht`
- Stats: `kills`/`k`, `assists`/`a`, `digs`/`d`
- Optional include flags: `on_2026_roster`, `include_2026`, `is_2026_roster`, `is_on_2026_roster`, `will_be_on_2026_roster`

## Customizing output
- **Logos**: drop new PNGs in `report_builder/logos/` and map names in `guide.yml` under `logo_map`.
- **Airports/Risk notes/Politics labels**: override per school in `guide.yml` under `airport_info`, `risk_watchouts`, `politics_label_overrides`.
- **Team name aliases**: adjust matching in `guide.yml` under `team_name_aliases` if your CSV uses different display names.
- **Player config**: set home lat/lon, target schools, and override maps in `config/players/*.yml`.
