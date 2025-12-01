# Coaches Cache System

## Overview

The coaches cache system allows you to fetch coaching staff data once and reuse it across multiple runs, dramatically speeding up the `create_team_pivot_csv.py` script.

Since coaching staff information changes infrequently (typically only during off-season), caching this data makes sense for regular scraping operations.

## Quick Start

### 1. Fetch Coaches (One-Time Setup)

```bash
# Fetch coaches for all 347 D1 teams and save to cache
python scripts/fetch_coaches.py
```

This creates `settings/coaches_cache.json` with all coaching staff data.

### 2. Use Cached Coaches

```bash
# Generate team pivot CSV using cached coaches (fast!)
python -m src.create_team_pivot_csv
```

By default, `create_team_pivot_csv.py` now uses cached coaches automatically.

## Commands

### Fetching Coaches

```bash
# Fetch all teams (initial setup)
python scripts/fetch_coaches.py

# Fetch specific teams only
python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas"

# Refresh entire cache (re-fetch all teams)
python scripts/fetch_coaches.py --refresh

# Update cache (only fetch teams not already cached)
python scripts/fetch_coaches.py --update

# Use custom cache file
python scripts/fetch_coaches.py --output settings/coaches_cache_2026.json
```

### Using the Cache

```bash
# Use cached coaches (default behavior)
python -m src.create_team_pivot_csv

# Don't use cache (empty coach columns)
python -m src.create_team_pivot_csv --no-cache

# Fetch coaches live (ignore cache, slow)
python -m src.create_team_pivot_csv --refresh-coaches
```

## Cache File Format

The cache is stored as JSON in `settings/coaches_cache.json`:

```json
{
  "generated_at": "2025-12-01T12:34:56.789",
  "teams": {
    "Stanford University": {
      "coaches": [
        {
          "name": "Kevin Hambly",
          "title": "Head Coach",
          "email": "khambly@stanford.edu",
          "phone": "650-723-4528"
        },
        {
          "name": "Denise Corlett",
          "title": "Associate Head Coach",
          "email": "dcorlett@stanford.edu",
          "phone": ""
        }
      ],
      "fetched_at": "2025-12-01T12:34:56.789",
      "roster_url": "https://gostanford.com/sports/womens-volleyball/roster"
    }
  }
}
```

## When to Refresh the Cache

You should refresh the coaches cache when:

1. **Start of a new season** (August) - coaching staff may have changed
2. **Mid-season coaching changes** - if you hear about staff changes
3. **After adding new teams** - use `--update` to fetch only new teams
4. **Cache file is old** - check `generated_at` timestamp

## Performance Comparison

| Method | Time (347 teams) | Notes |
|--------|------------------|-------|
| **Live fetch** (old way) | ~15-20 minutes | Fetches coaches during each run |
| **Cached coaches** (new way) | ~2-3 minutes | Reads from JSON file |
| **No coaches** | ~2 minutes | Skip coaches entirely |

## Troubleshooting

### Cache file not found

```
WARNING: Coaches cache file not found: settings/coaches_cache.json
INFO: Run 'python scripts/fetch_coaches.py' to create cache
INFO: Continuing without coaches data...
```

**Solution:** Run `python scripts/fetch_coaches.py` to create the cache.

### Some teams missing coaches

If some teams have no coaches in the cache, it may be because:
- The team's roster page doesn't have coaching staff listed
- The page structure isn't recognized by the parser
- The page requires JavaScript to render

You can inspect the cache file to see which teams have empty coach lists.

### Updating specific teams

```bash
# Re-fetch coaches for specific teams
python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas"
```

This will update those teams in the existing cache file.

## Integration with Workflow

### Typical Workflow (with cache)

```bash
# 1. Initial setup (once per season)
python scripts/fetch_coaches.py

# 2. Run scraper regularly (fast, uses cached coaches)
python -m src.run_scraper
python -m src.create_team_pivot_csv

# 3. Refresh coaches periodically (e.g., monthly)
python scripts/fetch_coaches.py --refresh
```

### Alternative Workflow (without cache)

If you prefer to always fetch fresh coach data:

```bash
# Always fetch coaches live
python -m src.create_team_pivot_csv --refresh-coaches
```

## Technical Details

### Modules

- **`scripts/fetch_coaches.py`** - CLI tool to fetch and cache coaches
- **`scraper/coaches_cache.py`** - Helper module to load cached data
- **`scraper/coaches.py`** - Core HTML parsing logic (unchanged)

### Cache Location

Default: `settings/coaches_cache.json`

This location is in the `settings/` directory alongside other configuration files, and can be committed to version control if desired.

### Cache Validation

The system doesn't validate cache age automatically. You're responsible for refreshing the cache when needed. Check the `generated_at` timestamp to see when the cache was last updated.

## Future Enhancements

Potential improvements:

- Auto-detect stale cache and prompt for refresh
- Parallel fetching for faster initial cache generation
- Cache validation and repair tools
- Integration with version control for team collaboration
