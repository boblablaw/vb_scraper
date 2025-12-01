# Unit Tests for Settings Package

This document describes the unit tests for the volleyball scraper's settings package.

## Overview

The `test_settings.py` file contains comprehensive unit tests to verify that:
1. Configuration data is correctly organized in the settings package
2. All modules can successfully import configuration data
3. Configuration data maintains internal consistency

## Running the Tests

### Basic Usage

```bash
# From the project root
python -m tests.test_settings
```

### With Dependencies Installed

If you have all dependencies installed (pandas, beautifulsoup4, requests), all tests will run:

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
python -m tests.test_settings
```

### Without Dependencies

The tests are designed to work even without the full dependency stack. Tests that require missing dependencies will be automatically skipped.

## Test Structure

### TestSettingsPackageImports

Tests that configuration data is correctly accessible from the settings package.

**Test Cases:**
- `test_teams_list_import` - Verifies TEAMS list structure and accessibility
- `test_outgoing_transfers_import` - Verifies OUTGOING_TRANSFERS list structure
- `test_rpi_team_name_aliases_import` - Verifies RPI_TEAM_NAME_ALIASES dictionary structure
- `test_raw_incoming_text_import` - Verifies RAW_INCOMING_TEXT string structure
- `test_all_exports_in_all` - Verifies __all__ contains expected exports

### TestDependentModuleImports

Tests that modules dependent on configuration data can successfully import from the settings package.

**Test Cases:**
- `test_run_scraper_imports_teams` - Verifies src/run_scraper.py can import TEAMS from teams_urls.py
- `test_team_analysis_imports_rpi_aliases` - Verifies scraper/team_analysis.py can import RPI_TEAM_NAME_ALIASES
- `test_rpi_lookup_imports_aliases` - Verifies scraper/rpi_lookup.py can import RPI_TEAM_NAME_ALIASES
- `test_transfers_imports_outgoing_transfers` - Verifies scraper/transfers.py can import OUTGOING_TRANSFERS
- `test_team_pivot_imports_outgoing_transfers` - Verifies src/create_team_pivot_csv.py can import OUTGOING_TRANSFERS
- `test_export_transfers_imports_outgoing_transfers` - Verifies src/create_transfers_csv.py can import OUTGOING_TRANSFERS
- `test_incoming_players_module_accessible` - Verifies year-based incoming_players_data system is accessible

### TestSettingsDataConsistency

Tests consistency and relationships between different settings data.

**Test Cases:**
- `test_teams_have_unique_names` - Verifies all team names are unique
- `test_teams_urls_are_valid` - Verifies all URLs start with http/https
- `test_rpi_aliases_map_to_valid_teams` - Verifies RPI aliases reference teams in TEAMS list
- `test_incoming_text_contains_conferences` - Verifies RAW_INCOMING_TEXT includes conferences from TEAMS

## Test Coverage

The test suite covers:

✅ **Settings Package Structure**
- Configuration files (teams_urls.py, transfers_config.py, rpi_team_name_aliases.py, incoming_players_data.py, year-specific incoming_players_data_YYYY.py)
- Package __init__.py exports
- Data types and structure validation
- Year-based URL and incoming players systems

✅ **Import Verification**
- Direct imports from settings package
- Imports by dependent modules (run_scraper, team_analysis, transfers, etc.)
- Cross-module import consistency

✅ **Data Validation**
- TEAMS list contains required fields (team, conference, url, stats_url) from teams_urls.py
- Year-based URL system (get_season_year, append_year_to_url, get_teams_with_year_urls)
- OUTGOING_TRANSFERS contains required fields (name, old_team, new_team)
- RPI_TEAM_NAME_ALIASES is properly formatted
- Year-based incoming players data system (automatic year selection)

✅ **Data Consistency**
- Team names are unique
- URLs are valid (start with http/https)
- RPI aliases reference actual teams
- Incoming player data includes known conferences

## Expected Results

When run successfully, you should see output similar to:

```
test_all_exports_in_all ... ok
test_outgoing_transfers_import ... ok
test_raw_incoming_text_import ... ok
test_rpi_team_name_aliases_import ... ok
test_teams_list_import ... ok
test_export_transfers_imports_outgoing_transfers ... ok
test_incoming_players_module_accessible ... ok
test_rpi_lookup_imports_aliases ... skipped (optional dependency)
test_run_scraper_imports_teams ... skipped (optional dependency)
test_team_analysis_imports_rpi_aliases ... skipped (optional dependency)
test_team_pivot_imports_outgoing_transfers ... ok
test_transfers_imports_outgoing_transfers ... ok
test_incoming_text_contains_conferences ... ok
test_rpi_aliases_map_to_valid_teams ... ok
test_teams_have_unique_names ... ok
test_teams_urls_are_valid ... ok

----------------------------------------------------------------------
Ran 16 tests in 0.XXXs

OK (skipped=3)
```

## Troubleshooting

### ImportError: No module named 'settings'

Make sure you're running the tests from the project root directory:

```bash
cd /path/to/vb_scraper
python -m tests.test_settings
```

### Tests Failing After Configuration Changes

If you've modified configuration files, tests may fail if:
- Required dictionary keys are missing
- Data types have changed
- The first entry in TEAMS or OUTGOING_TRANSFERS has changed

Update the relevant test assertions to match your new configuration.

### All Dependent Module Tests Skipped

This is expected if you don't have pandas, beautifulsoup4, or requests installed. The core settings import tests will still run and verify the package structure.

## Adding New Tests

When adding new configuration files to the settings package:

1. Add import test to `TestSettingsPackageImports`
2. Add export to test in `test_all_exports_in_all`
3. Add dependent module test if applicable
4. Add consistency tests if applicable

Example:

```python
def test_new_config_import(self):
    """Test that NEW_CONFIG is correctly imported and accessible."""
    from settings import NEW_CONFIG
    
    self.assertIsInstance(NEW_CONFIG, dict)
    self.assertGreater(len(NEW_CONFIG), 0)
```

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```bash
# Run tests and exit with appropriate code
python -m tests.test_settings
```

Exit code 0 indicates all tests passed; non-zero indicates failure.
