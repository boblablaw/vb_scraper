# Test Data

This directory contains team lists for testing the scraper on subsets of teams.

## Usage

```bash
# Run scraper with a test team list
python run_scraper.py --teams-file test_data/sample_15_teams.txt

# Or use --team flag for individual teams
python run_scraper.py --team "University of Texas at San Antonio"
```

## Sample Files

- **`sample_15_teams.txt`** - Random sample of 15 teams for quick testing
- **`sample_fixed_teams.txt`** - Teams with known issues (for regression testing)
- **`sample_js_rendered.txt`** - Teams with JavaScript-rendered rosters (future work)

## Creating Custom Test Lists

Create a text file with one team name per line (must match exact names in `settings/teams.py`):

```
University of Texas at San Antonio
Bethune-Cookman University
University of Wisconsin-Green Bay
```

## Notes

- Files in this directory are gitignored by default (except `sample_*.txt` and `README.md`)
- Use these for testing before running full scraper (which takes ~15 minutes)
- Always include problem teams in your test samples to catch regressions
