# Incoming Players Data Management

This directory contains year-specific incoming players data stored as plain text files that are automatically selected based on the current date.

## How It Works

The selector now lives in `scripts.helpers.incoming_players_data.py` (imported by `settings`). It chooses the correct text file based on date ranges:

### Date-Based Selection Rules

| Date Range                | File Used                           | Data For |
|--------------------------|-------------------------------------|----------|
| Aug 1, 2024 - Jul 31, 2025 | `incoming_players_2025.txt`   | 2025 season |
| Aug 1, 2025 - Jul 31, 2026 | `incoming_players_2026.txt`   | 2026 season |
| Aug 1, 2026 - Jul 31, 2027 | `incoming_players_2027.txt`   | 2027 season |

**Logic**: If current month >= August, use next year's data. Otherwise use current year's data.

## File Structure

Each year-specific file is plain text (e.g., `incoming_players_2026.txt`) with the contents of `RAW_INCOMING_TEXT_YYYY`.

## Adding Incoming Players Data

### For Current/Active Season

1. Identify which file is currently active (check date against table above)
2. Edit the appropriate `incoming_players_YYYY.txt` file
3. Add players in the format:
   ```
   Conference Name:
   Player Name - School Name - Position (Club)
   ```

### For Future Season

1. Create a new file: `incoming_players_YYYY.txt` where YYYY is the year
2. Use this template:

```
Conference Name:
Player Name - School Name - Position (Club)
```

3. The system will automatically use it when the date range is active

## Data Format

### Required Format

```
Conference Name:
Player Name - School Name - Position (Club)
Player Name - School Name - Position (Club)

Next Conference Name:
Player Name - School Name - Position (Club)
```

### Example

```
Atlantic Coast Conference (ACC):
Ella Andrews - Stanford University - MB (Legacy)
Sarah Hickman - Stanford University - OPP (Houston Juniors)
Simone Roslon - Stanford University - OH (SC Rockstar)

Big Ten Conference:
Jane Doe - Ohio State University - S (Premier Ohio)
John Smith - Penn State University - OH (PRVBC)
```

### Position Codes

- **S** - Setter
- **OH** - Outside Hitter  
- **RS** / **OPP** - Right Side / Opposite
- **MB** - Middle Blocker
- **DS** / **Libero** - Defensive Specialist / Libero

Multiple positions can be separated by `/` (e.g., `OH/RS`, `S/DS`)

## Testing the Selector

To verify which year's data is currently being used:

```bash
python -m scripts.helpers.incoming_players_data
```

Current date: December 01, 2025
Using incoming players data for: 2026
Data length: 45230 characters
```

## Fallback Behavior

If the required year's file doesn't exist, the system automatically falls back to `incoming_players_data_2025.py` with a warning message.

## Integration

The incoming players data is used by:

1. **`scraper/incoming_players.py`** - Parses the raw text into structured data
2. **`src/create_team_pivot_csv.py`** - Matches incoming players to teams for roster projections

No code changes are needed to switch years - it happens automatically based on the date.

## Maintenance Schedule

### July (Prepare for New Season)

1. Create next year's file (e.g., `incoming_players_data_2026.py`)
2. Begin populating with known commitments and transfers
3. Test: `python -m scripts.helpers.incoming_players_data`

### August 1 (Season Transition)

- System automatically switches to new year's data
- Verify the switch happened correctly
- Continue updating data as more players commit

### Throughout Season

- Keep data current with latest commits and transfers
- Regular validation: `python validation/validate_data.py`

## Common Issues

### "Warning: Could not load incoming players data for YYYY"

**Cause**: The file for the current year doesn't exist yet.

**Solution**: Create `incoming_players_data_YYYY.py` using the template above.

### Tests Failing on RAW_INCOMING_TEXT

**Cause**: Active year's file has insufficient or malformed data.

**Solution**: Ensure the active year's file has properly formatted conference and player data.

## File Naming Convention

- **Format**: `incoming_players_data_YYYY.py`
- **Variable**: `RAW_INCOMING_TEXT_YYYY`
- **Year**: Use the season year (e.g., 2025 for 2024-2025 season)

## See Also

- **Manual Rosters**: `MANUAL_ROSTERS_README.md` - For JavaScript-rendered sites
- **Transfers**: `transfers.json` - Outgoing transfer tracking
- **Teams**: `teams.py` - D1 team roster and stats URLs
