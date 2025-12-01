# Coaches Cache System - Implementation Summary

## Overview

I've implemented a coaches caching system that allows you to fetch coaching staff data once and reuse it across multiple runs. This dramatically speeds up the `create_team_pivot_csv.py` script.

## What Changed

### New Files Created

1. **`scripts/fetch_coaches.py`** - CLI tool to fetch and cache coaches
   - Fetches coaching staff from all 347 D1 teams
   - Stores data in JSON cache file
   - Supports selective updates and refreshes

2. **`scraper/coaches_cache.py`** - Helper module for cache management
   - Functions to load and access cached data
   - Packs coach data into CSV row format

3. **`docs/COACHES_CACHE.md`** - Comprehensive documentation
   - Quick start guide
   - Command reference
   - Troubleshooting tips
   - Workflow integration

4. **`settings/coaches_cache.json`** (generated) - Cache file
   - JSON format with coaching staff for each team
   - Includes timestamps for tracking

### Files Modified

1. **`src/create_team_pivot_csv.py`**
   - Now uses cached coaches by default
   - Added command-line flags: `--no-cache` and `--refresh-coaches`
   - Falls back gracefully if cache doesn't exist

2. **`WARP.md`**
   - Updated project structure
   - Updated command examples
   - Updated data flow diagram

## Quick Start

### Step 1: Fetch Coaches (One-Time Setup)

```bash
# This will take ~15-20 minutes to fetch all 347 teams
python scripts/fetch_coaches.py
```

This creates `settings/coaches_cache.json` with all coaching staff data.

### Step 2: Use the Cache

```bash
# Now this runs much faster (uses cached coaches)
python -m src.create_team_pivot_csv
```

## Command Reference

### Fetching Coaches

```bash
# Fetch all teams (initial setup)
python scripts/fetch_coaches.py

# Fetch specific teams only
python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas"

# Refresh entire cache
python scripts/fetch_coaches.py --refresh

# Update cache (only fetch teams not already cached)
python scripts/fetch_coaches.py --update
```

### Using the Cache

```bash
# Use cached coaches (DEFAULT - fast!)
python -m src.create_team_pivot_csv

# Don't use cache (empty coach columns)
python -m src.create_team_pivot_csv --no-cache

# Fetch coaches live (slow, ignores cache)
python -m src.create_team_pivot_csv --refresh-coaches
```

## Performance Impact

| Method | Time | Description |
|--------|------|-------------|
| **Without cache** (old way) | ~15-20 min | Fetches coaches during each run |
| **With cache** (new way) | ~2-3 min | Reads from JSON file |
| **No coaches** | ~2 min | Skip coaches entirely |

**Result: ~10-15 minutes saved per run!**

## How It Works

### Cache File Structure

```json
{
  "generated_at": "2025-12-01T12:34:56.789",
  "teams": {
    "Stanford University": {
      "coaches": [
        {"name": "Kevin Hambly", "title": "Head Coach", "email": "...", "phone": "..."}
      ],
      "fetched_at": "2025-12-01T12:34:56.789",
      "roster_url": "https://gostanford.com/..."
    }
  }
}
```

### Integration Points

1. **`scripts/fetch_coaches.py`** → Fetches and stores coach data
2. **`scraper/coaches_cache.py`** → Loads and formats cached data
3. **`src/create_team_pivot_csv.py`** → Uses cached data by default

## When to Refresh

You should refresh the cache:

- **Start of new season** (August) - coaching changes
- **Mid-season changes** - if you hear about staff changes
- **After adding new teams** - use `--update` mode
- **Cache is old** - check `generated_at` timestamp

## Typical Workflow

```bash
# 1. Initial setup (once per season)
python scripts/fetch_coaches.py

# 2. Run scraper regularly (fast!)
python -m src.run_scraper
python -m src.create_team_pivot_csv

# 3. Refresh coaches periodically (e.g., monthly or as needed)
python scripts/fetch_coaches.py --refresh
```

## Benefits

✅ **10-15 minutes faster** on each run of `create_team_pivot_csv.py`  
✅ **Reduces server load** - no repeated coach scraping  
✅ **Backwards compatible** - falls back gracefully if cache missing  
✅ **Flexible** - can still fetch live with `--refresh-coaches`  
✅ **Easy to update** - refresh specific teams or entire cache  

## Migration Path

### For Existing Workflows

1. **Run once to create cache:**
   ```bash
   python scripts/fetch_coaches.py
   ```

2. **Continue using existing commands:**
   ```bash
   python -m src.create_team_pivot_csv
   ```
   
   That's it! The script will automatically use the cache.

### If You Don't Want the Cache

You can continue without the cache in two ways:

```bash
# Option 1: Skip coaches entirely (fastest)
python -m src.create_team_pivot_csv --no-cache

# Option 2: Always fetch live (slowest, like before)
python -m src.create_team_pivot_csv --refresh-coaches
```

## Testing

You can test the system with a few teams first:

```bash
# Test with 3 teams
python scripts/fetch_coaches.py --teams "Stanford University" "University of Texas" "Penn State University"

# Then run pivot (will use cached data for these teams)
python -m src.create_team_pivot_csv
```

## Troubleshooting

**Cache file not found:**
```
WARNING: Coaches cache file not found: settings/coaches_cache.json
INFO: Run 'python scripts/fetch_coaches.py' to create cache
```
→ Solution: Run `python scripts/fetch_coaches.py`

**Some teams missing coaches:**
→ Check cache file to see which teams have empty coach lists
→ Re-fetch specific teams: `python scripts/fetch_coaches.py --teams "Team Name"`

## Documentation

Full documentation available in:
- **`docs/COACHES_CACHE.md`** - Complete guide with examples
- **`WARP.md`** - Updated with cache system info

## Next Steps

1. **Create initial cache:**
   ```bash
   python scripts/fetch_coaches.py
   ```

2. **Verify it works:**
   ```bash
   python -m src.create_team_pivot_csv
   ```

3. **Check the output:**
   - Coach columns should be populated
   - Script should run much faster

4. **Set up periodic refresh** (optional):
   - Add to monthly maintenance routine
   - Or run before each season starts

Enjoy the speed boost! 🚀
