# GitHub Usage & Workflow

This project combines data scraping, an API, a web app, and a PDF builder. Use the guidelines below when collaborating via GitHub.

## Branches & PRs
- **Main** is treated as deployable. Keep it green.
- Create feature branches (`feature/...` or `chore/...`) and open PRs with a short summary of scope and risk.
- Include a brief test note in PRs (e.g., “Ran create_team_pivot against sample CSV”, “Not run; offline changes only”).

## Testing & Quality
- Python: prefer `python -m scripts.create_team_pivot ...` and `python -m report_builder.cli ...` as smoke checks after data-facing changes; run targeted unit tests if you add any.
- Frontend: `npm run lint` / `npm run test` when UI code changes.
- Backend: `uvicorn backend.main:app --reload` for manual checks; add pytest cases if you change API behavior.

## Data & Assets
- Large/generated files live under `exports/`, `assets/`, and `data/` and are **not** meant for long-lived branches unless required. Keep CSVs and caches small or git-ignored.
- Secrets/tokens are not stored here; scraping cookies live under `scripts/cookies/` locally.

## Coding Notes
- Shared helpers live in `scripts/helpers`. Import from there instead of duplicating utilities.
- Keep `settings/teams.json` as the single source of truth for team metadata, aliases, logos, and coaches.
- When adding new scripts, prefer argparse entrypoints and place shared logic in helpers.

## Common Commands
- Merge rosters+stats: `python -m scripts.merge_ncaa_wvb_stats_and_rosters --stats ... --rosters ... --output exports/ncaa_wvb_merged_2025.csv`
- Build team pivot: `python -m scripts.create_team_pivot`
- Fetch coaches (with photos): `python -m scripts.fetch_coaches`
- Build PDF: `python -m report_builder.cli`
