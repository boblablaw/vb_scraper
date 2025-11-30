# Failed Class Normalization Analysis

## Overview
Found **57 players** with raw class data that failed to normalize properly.

## Root Causes

### 1. First Year (FY) Variations - 41 players (~72%)
Some schools use "First Year" (FY) instead of "Freshman" (Fr):
- `Fy.` - 26 occurrences (Northwestern University)
- `Fy` - 4 occurrences (Columbia University)
- `FY` - 3 occurrences (Columbia University)
- `RFr.` - 2 occurrences (Northwestern)
- `R-Fy.` - 1 occurrence (Northwestern)
- `Rf.` - 7 occurrences (Northwestern)

**Schools affected**: Northwestern University, Columbia University

**Fix needed**: Update `normalize_class()` function in `scraper/utils.py` to handle:
- `FY`, `Fy`, `Fy.` → `Fr`
- `RFr.`, `R-Fy.`, `Rf.` → `R-Fr`

### 2. Non-Standard Year Format - 1 player
- `6th` - 1 occurrence (Boise State University: Arianna Bilby)

**Note**: This might be a legitimate 6th year player. Should map to `Fifth` or `Gr`.

### 3. Club Team Names Instead of Class - 15 players (~26%)
The scraper is picking up club volleyball team names from the roster page instead of class year:

Examples:
- `CITY Volleyball Club` (Boston College)
- `Coast` (Boston College)
- `Drive Nation` (Boston College)
- `Legacy Volleyball Club` (Boston College)
- `NorCal` (Boston College)
- `Northeast Volleyball Club` (Boston College)
- `OTVA` (Boston College)
- `Skyline` (Boston College)
- `Team Indiana` (Boston College)
- `Vision` (Boston College)
- `Vision Volleyball Club` (Boston College)

**Schools affected**: Primarily Boston College

**Root cause**: Boston College's roster HTML structure puts club team info in a location where the parser expects class year data.

**Fix needed**: Update roster parser to:
1. Validate that extracted "class_raw" looks like a year (contains Fr/So/Jr/Sr/Freshman/Sophomore/etc)
2. Skip fields that look like club names (contain "Club", "Volleyball", "Nation", etc.)
3. Look for alternative class data location on Boston College roster pages

## Recommended Fixes

### Priority 1: Add FY/Fy Normalization
Add to `normalize_class()` in `scraper/utils.py`:

```python
# First Year variations
if norm in ('fy', 'fy.', 'firstyear', 'first year'):
    return 'Fr'
if norm in ('rfy', 'r-fy', 'rfy.', 'r-fy.', 'rfr.', 'rf.'):
    return 'R-Fr'
```

**Impact**: Fixes 41/57 failures (72%)

### Priority 2: Fix Boston College Parser
Add validation in roster parser to detect and skip club names:

```python
CLUB_KEYWORDS = ['club', 'volleyball', 'vbc', 'nation', 'team']

def looks_like_club_name(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CLUB_KEYWORDS)

# In parser:
if looks_like_club_name(class_raw):
    class_raw = ""  # Clear invalid data
```

**Impact**: Fixes 15/57 failures (26%)

### Priority 3: Handle "6th" Year
Add to normalization:

```python
if norm in ('6th', 'sixth', 'sixth year'):
    return 'Fifth'  # or 'Gr' depending on convention
```

**Impact**: Fixes 1/57 failures (2%)

## Teams Requiring Special Attention

### Northwestern University (34 players affected)
Uses "Fy." and "Rf." notation consistently. Once normalization is added, all should parse correctly.

### Columbia University (7 players affected)  
Uses "FY" notation. Once normalization is added, all should parse correctly.

### Boston College (15 players affected)
Parser is extracting club names instead of class years. Requires parser-level fix, not just normalization.

**Recommendation**: Check Boston College's HTML structure manually to identify correct class field location.

## Testing Checklist

After implementing fixes:
1. ✅ Verify Northwestern parses "Fy." correctly
2. ✅ Verify Columbia parses "FY" correctly
3. ✅ Verify Boston College extracts class, not club names
4. ✅ Re-run validation to confirm 0 failed normalizations
5. ✅ Verify no regressions in other teams' class parsing

## Files Modified
- `scraper/utils.py` - Update `normalize_class()` function
- `scraper/roster.py` - Add club name validation
- `validation/validate_data.py` - Used to detect the issue

---

**Created**: 2025-11-30  
**Total Affected**: 57 players (1.2% of total)  
**Estimated Fix Time**: 30 minutes  
**Priority**: Medium (low percentage but easy fix)
