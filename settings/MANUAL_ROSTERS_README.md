# Manual Roster Data

For teams with JavaScript-rendered rosters that can't be scraped automatically, you can manually enter roster data in `manual_rosters.csv`.

## Quick Start

1. **Edit `manual_rosters.csv`** - Add player data for teams that failed to scrape
2. **Run merge script** - `python merge_manual_rosters.py`
3. **Done!** - Manual data is now included in the main export

## File Format

`manual_rosters.csv` uses a simple CSV format:

```csv
Team,Name,Position,Class,Height
University of Alabama,Jane Doe,OH,Jr,6-2
University of Alabama,John Smith,S,So,5-10
University of Arkansas,Sarah Johnson,MB,Sr,6-3
```

### Required Columns

- **Team** - Exact team name (must match `settings/teams.py`)
- **Name** - Player's full name
- **Position** - Position code(s): S, OH, RS, MB, DS, L
- **Class** - Class year: Fr, So, Jr, Sr, R-Fr, R-So, R-Jr, R-Sr, Gr
- **Height** - Height in F-I format: 6-2, 5-10, etc.

### Tips

- Leave template rows with empty names - they'll be ignored
- Use exact team names from the failed teams list
- Position codes are flexible: OH, OH/RS, S/DS all work
- Heights can be 6-2, 6'2, 6′2″ - they'll be normalized

## Workflow

### 1. Identify Failed Teams

After running the scraper, check which teams failed:

```bash
python run_scraper.py 2>&1 | grep "No players parsed for team"
```

Or use the pre-generated list in `test_data/sample_js_rendered.txt` (42 teams)

### 2. Add Manual Data

Edit `settings/manual_rosters.csv` and add players for one or more teams:

```csv
Team,Name,Position,Class,Height
University of Alabama,Emma Anderson,S,Jr,5-11
University of Alabama,Sarah Williams,OH,So,6-0
University of Alabama,Jessica Brown,MB,Fr,6-3
```

### 3. Merge with Scraped Data

Run the merge script:

```bash
python merge_manual_rosters.py
```

This will:
- Load manual roster data
- Remove any existing data for manual teams from scraped export
- Add manual roster entries with proper structure
- Write updated export to `exports/d1_rosters_2026_with_stats_and_incoming.tsv`

### 4. Regenerate Display CSV

After merging, regenerate the display CSV:

```bash
python create_display_csv.py
```

## What Gets Populated

Manual entries will have:
- ✅ Team, Conference, URLs (from `settings/teams.py`)
- ✅ Name, Position, Class, Height (from your manual data)
- ✅ Position flags (Is Setter, Is Pin Hitter, etc.) - auto-detected from position
- ❌ Stats (kills, assists, digs, etc.) - not available without scraping
- ❌ Coach info - not available without scraping
- ❌ Transfer flags - not available without scraping

This is sufficient for basic roster analysis (position counts, height averages, etc.)

## Example Output

After running merge script:

```
Manual Roster Merge Tool
================================================================================

Loaded scraped data: 3489 rows from 175 teams
Loaded manual data: 45 players from 3 teams

Removed 3 teams from scraped data (will be replaced with manual data)

Merged data written to: exports/d1_rosters_2026_with_stats_and_incoming.tsv
  Total players: 3534
  Total teams: 178
  Manual teams added: 3

Manual teams:
  - University of Alabama: 15 players
  - University of Arkansas: 14 players
  - University of Florida: 16 players
```

## Current Status

**42 teams** with JavaScript-rendered rosters need manual data entry:

**SEC (12 teams)**: Alabama, Arkansas, Florida, Georgia, Kentucky, LSU, Missouri, Oklahoma, South Carolina, Tennessee, Texas, Vanderbilt

**WCC (7 teams)**: Gonzaga, Portland, San Diego, San Francisco, Santa Clara, Seattle, Washington State

**Others (23 teams)**: Coastal Carolina, Denver, Furman, James Madison, Lafayette, Lamar, Le Moyne, LIU, Marshall, Mercer, Missouri-Kansas City, New Mexico, New Orleans, North Dakota, Oregon State, Pacific, South Dakota, St. Thomas, The Citadel, Troy, Utah State, Utah Tech, Wyoming

See `test_data/sample_js_rendered.txt` for complete list.
