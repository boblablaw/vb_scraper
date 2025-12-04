# Report Builder

Generate a personalized “Ultimate School Guide” PDF for a volleyball player. It pulls roster/stats/pivot data, applies school metadata and travel math, and renders a multi-section PDF with logos, maps, fit rankings, and school detail pages.

## What it does
- Loads per-player settings (`config/players/*.yml`) for name/bio, home location, and target school list.
- Merges static defaults plus optional overrides from `config/guide.defaults.yml` and `config/guide.yml` (team name aliases, politics labels, airport info, risk notes, coach overrides).
- Reads data:
  - `exports/team_pivot.csv` (conference, offense, RPI, record, projected setter count, vb_opp score)
  - `exports/rosters_and_stats.csv` (roster and stats)
  - `settings/coaches_cache.json` (staff/contact cache)
- Computes travel (drive/flight distance/time) from the player’s home lat/lon.
- Filters to the player’s selected schools and renders the PDF with logos, fit tables, travel matrix, and per-school pages (including roster snapshot and notes page).
- Outputs to `report_builder/exports/Ultimate_School_Guide_{PlayerName}.pdf` unless overridden.

## Requirements
- Python 3.11+ (tested with 3.13)
- Packages: `reportlab`, `pandas`, `pyyaml` (optional but recommended), `pytest` for tests.
  - Install: `pip install -r requirements.txt` (or add these to your env).
- Data files expected at repository root unless overridden:
  - `exports/team_pivot.csv`
  - `exports/rosters_and_stats.csv`
  - `settings/coaches_cache.json`
- Assets:
- Logos: `report_builder/logos/` (PNG files named per `logo_map` in `report_builder/config/guide.defaults.yml`)
  - Map: `report_builder/assets/us_map_blank.png`

## Quick start
```bash
python -m report_builder.cli
```
This uses defaults: Molly Beatty player config and outputs `report_builder/exports/Ultimate_School_Guide_Molly_Beatty.pdf`.

## Custom player / paths
```bash
python -m report_builder.cli \
  --player-settings report_builder/config/players/your_player.yml \
  --team-pivot exports/team_pivot.csv \
  --rosters exports/rosters_and_stats.csv \
  --logos-dir report_builder/logos \
  --us-map report_builder/assets/us_map_blank.png \
  --output report_builder/exports/custom.pdf
```

## Player settings format
See `config/players/molly_beatty.yml` or `config/players/README.md`. Key fields:
- `player`: name, height, handedness, position, home_city/home_state, home_lat/home_lon.
- `schools`: list of school names (must match the `name` field in `build_ultimate_guide.py`).
- `overrides` (optional): `risk_watchouts`, `airport_info`, `politics_label_overrides`, `team_name_aliases`.

## Tests
```bash
pytest tests/test_player_settings.py
```

## Entrypoints
- CLI: `python -m report_builder.cli`
- Programmatic: `report_builder.pipelines.build_pdf(GuideConfig(...))`
