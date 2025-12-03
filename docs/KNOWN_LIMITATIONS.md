# Known Limitations

Current state: core scraping is working for nearly all teams. Remaining gaps are limited to edge cases where pages are JS-only, behind bot protection, or have unstable hosting.

## Known Gaps
- **Heavy JS / redirects**: A few sites require a browser (Selenium/Playwright) because the roster HTML never renders server-side. Use manual entry in `settings/manual_rosters.csv` or capture HTML via `scripts/snapshot_html.py` + browser automation if needed.
- **Occasional bot blocks / 4xx**: Some schools intermittently return 403/404/redirects. Check `exports/scraper.log` and try again with updated URLs from the athletics site.
- **Logo fallbacks**: If Commons fails, logos fall back to team sites. Any `_BAD`-suffixed logos will be retried; remaining misses are listed in `logos/missing_school_logos.txt`.

## Workarounds
- **Manual data**: Add rows to `settings/manual_rosters.csv` for any team that refuses to render without JS.
- **Targeted runs**: Use `python -m src.run_scraper --team "School Name"` or the logo script `--team` flag for focused retries.
- **HTML snapshots**: `scripts/snapshot_html.py` can grab HTML for offline parser tweaks.

## Monitoring
- Watch `exports/scraper.log` for new parsing failures.
- Run `python validation/validate_data.py` after major runs.
- Review `settings/teams_urls.py` periodically for domain/path changes.

Last Updated: 2025-12-03  
Last Full Scrape: 2025-11-29  
Coverage: 305/347 (87.9%)
