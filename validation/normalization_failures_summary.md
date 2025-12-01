# Normalization Failures - Complete Analysis

## Summary

Total normalization failures across all fields:
- **Position**: 55 players (1.2%)
- **Height**: 14 players (0.3%)
- **Class**: 57 players (1.2%)
- **Total**: 126 failures out of 4,735 players (2.7%)

## Position Normalization Failures (55 players)

### Root Causes

#### 1. Numbers Instead of Positions (31 players - 56%)
The parser is extracting jersey numbers or page IDs instead of positions:
- `110`, `130`, `144`, `150`, `154`, `169`, `185`, `191`, `216`, `247`, `275`, `308`, `335`, `356`, `377`, etc.

**Schools affected**: 
- University of Central Florida
- University of Cincinnati  
- Old Dominion University

**Root cause**: These schools' HTML has numbers in fields where the parser expects position data.

#### 2. Position + Height Combined (19 players - 35%)
Parser extracting position and height together:
- `Left Side LS 5'6"`
- `Left Side LS 5'8"`
- `Left Side LS 5'9"`
- `Left Side LS 5'10"`
- `Left Side LS 6'1"`
- `Left Side LS 6'2"`
- `Middle MB 5'10"`
- `Middle MB 6'0"`
- `Middle MB 6'1"`
- `Middle MB 6'2"`
- `Outside Hitter OH 5'10"`
- `Outside Hitter OH 5'11"`
- `Outside Hitter OH 5'7"`
- `Outside Hitter OH 6'0"`
- `Outside Hitter OH 6'1"`
- `Outside Hitter OH 6'3"`
- `LB 5'6"`

**Schools affected**: Coppin State University

**Root cause**: Coppin State's HTML structure combines position and height in one field.

#### 3. Other Invalid Data (5 players - 9%)
- `A` (1 player)
- `Creative Video • First Season` (1 player)
- `Defense/Libero 1` (1 player)
- `Defense/Libero 2` (1 player)  
- `Libero/Defensive Specialist 10` (1 player)

**Fix Strategy**:
1. **Numbers**: Add validation to skip pure numeric values
2. **Combined position+height**: Parse and split these formats (e.g., extract "LS" from "Left Side LS 5'6"")
3. **Other**: Add more position aliases (e.g., "Defense" → "DS", "LB" → "DS")

## Height Normalization Failures (14 players)

### Root Causes

#### 1. Jersey Number Column Header (11 players - 79%)
Parser extracting column header "Jersey Number" instead of height:
- `Jersey Number` (11 occurrences)

**Schools affected**: Stanford University

**Root cause**: Stanford's roster HTML structure is not being parsed correctly - the parser is hitting table headers instead of data cells.

#### 2. Team Name Instead of Height (1 player)
- `2025 Volleyball Team` (1 player)

**Schools affected**: Unknown

#### 3. Malformed Height (1 player)
- `0' 0''` (1 player)

**Root cause**: Height data is corrupted or placeholder.

#### 4. Invalid Character (1 player)
- `é` (1 player - looks like encoding issue)

**Fix Strategy**:
1. **Jersey Number**: Fix Stanford parser to skip header rows
2. **Team name**: Add validation to reject non-height strings
3. **Malformed**: Skip `0' 0''` or similar zero heights
4. **Encoding**: Improve Unicode handling

## Class Normalization Failures (57 players)

### Already documented in `failed_class_normalization_analysis.md`:
- 41 players: FY/Fy variations (Northwestern, Columbia)
- 15 players: Club names (Boston College)
- 1 player: "6th" year (Boise State)

## Breakdown by School

### Teams with Multiple Issues

**University of Central Florida (8+ position failures)**
- Extracting numbers instead of positions
- Part of the 100% data loss group

**University of Cincinnati (8+ position failures)**
- Extracting numbers instead of positions
- Part of the 100% data loss group

**Old Dominion University (5+ position failures)**
- Extracting numbers instead of positions
- Part of the 100% data loss group

**Stanford University (11 height failures)**
- Extracting "Jersey Number" header text
- Part of the 100% data loss group

**Coppin State University (19 position failures)**
- Position and height combined in one field
- Partial parsing working

**Northwestern University (34 class failures)**
- Uses "Fy." notation
- Otherwise good data quality

**Columbia University (7 class failures)**
- Uses "FY" notation
- Otherwise good data quality

**Boston College (15 class failures)**
- Extracting club names instead of class
- Otherwise good data quality

## Recommended Fixes

### Priority 1: High Impact, Easy Fix
1. **Add FY/Fy normalization** - Fixes 41 class failures (72% of class issues)
   - File: `scraper/utils.py`
   - Time: 10 minutes

### Priority 2: Medium Impact, Medium Effort
2. **Add position + height splitter** - Fixes 19 position failures (35% of position issues)
   - File: `scraper/roster.py`
   - Extract position code from combined strings like "Outside Hitter OH 5'11""
   - Time: 30 minutes

3. **Skip numeric positions** - Fixes 31 position failures (56% of position issues)
   - File: `scraper/roster.py`
   - Validate that position field is not a pure number
   - Time: 15 minutes

4. **Add club name detection** - Fixes 15 class failures (26% of class issues)
   - File: `scraper/roster.py`
   - Skip fields containing "Club", "Volleyball", "Nation", etc.
   - Time: 15 minutes

### Priority 3: Low Impact but Important
5. **Fix Stanford parser** - Fixes 11 height failures
   - File: `scraper/roster.py`
   - Ensure parser skips table headers
   - Time: 30 minutes (requires understanding Stanford's HTML)

6. **Add position aliases** - Fixes 5 position failures
   - File: `scraper/utils.py`
   - Add: "Defense" → "DS", "LB" → "DS", etc.
   - Time: 10 minutes

## Overall Assessment

**Good News**:
- Only 2.7% of players have normalization failures
- Most failures are concentrated in a few schools
- Many fixes are straightforward

**Pattern Identified**:
The schools with position/height failures are the SAME schools with 100% data loss:
- UCF, Cincinnati, Old Dominion, Stanford

This suggests the parser isn't matching their HTML structure at all, so it's extracting garbage data. Fixing the parser for these schools will eliminate most normalization failures.

## Implementation Priority

1. ✅ **Quick wins** (1 hour total):
   - FY/Fy normalization
   - Skip numeric positions
   - Club name detection
   - Position aliases
   - **Impact**: Fixes ~70 failures (55% of all failures)

2. 📋 **Medium effort** (2-3 hours):
   - Position + height splitter
   - Stanford parser fix
   - **Impact**: Fixes ~30 failures (24% of all failures)

3. 🔧 **Long-term** (as part of major parser overhaul):
   - Fix UCF, Cincinnati, Old Dominion parsers
   - **Impact**: Fixes ~25 failures (20% of all failures) + enables full data extraction

---

**Created**: 2025-11-30  
**Total Affected**: 126 players (2.7%)  
**Quick Win Potential**: 70 failures fixed in 1 hour (55% resolution)
