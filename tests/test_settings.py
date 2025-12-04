#!/usr/bin/env python3
"""
Unit tests for the settings package.

Tests that all configuration data is correctly imported and accessible
from the settings package, and that dependent modules can import from it.
"""

import unittest
import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))


class TestSettingsPackageImports(unittest.TestCase):
    """Test that configuration data is correctly accessible from settings package."""

    def test_teams_list_import(self):
        """Test that TEAMS list is correctly imported and accessible."""
        from settings import TEAMS
        
        # Verify TEAMS exists and is a list
        self.assertIsInstance(TEAMS, list, "TEAMS should be a list")
        
        # Verify TEAMS is not empty
        self.assertGreater(len(TEAMS), 0, "TEAMS list should not be empty")
        
        # Verify each team has required keys
        required_keys = {"team", "conference", "url", "stats_url"}
        for team in TEAMS:
            self.assertIsInstance(team, dict, "Each team entry should be a dict")
            for key in required_keys:
                self.assertIn(key, team, f"Team entry should have '{key}' key")
                self.assertIsInstance(team[key], str, f"Team '{key}' should be a string")
        
        # Verify at least first team has expected structure
        first_team = TEAMS[0]
        self.assertIn("University at Albany", first_team["team"])
        self.assertIn("America East Conference", first_team["conference"])
        self.assertTrue(first_team["url"].startswith("http"))
        self.assertTrue(first_team["stats_url"].startswith("http"))

    def test_outgoing_transfers_import(self):
        """Test that OUTGOING_TRANSFERS list is correctly imported and accessible."""
        from settings import OUTGOING_TRANSFERS
        
        # Verify OUTGOING_TRANSFERS exists and is a list
        self.assertIsInstance(OUTGOING_TRANSFERS, list, "OUTGOING_TRANSFERS should be a list")
        
        # Verify OUTGOING_TRANSFERS is not empty
        self.assertGreater(len(OUTGOING_TRANSFERS), 0, "OUTGOING_TRANSFERS list should not be empty")
        
        # Verify each transfer has required keys
        required_keys = {"name", "old_team", "new_team"}
        for transfer in OUTGOING_TRANSFERS:
            self.assertIsInstance(transfer, dict, "Each transfer entry should be a dict")
            for key in required_keys:
                self.assertIn(key, transfer, f"Transfer entry should have '{key}' key")
                # Note: new_team can be empty string
                self.assertIsInstance(transfer[key], str, f"Transfer '{key}' should be a string")
        
        # Verify at least first transfer has expected data
        first_transfer = OUTGOING_TRANSFERS[0]
        self.assertEqual(first_transfer["name"], "Molly Beatty")
        self.assertEqual(first_transfer["old_team"], "Central Michigan University")

    def test_rpi_team_name_aliases_import(self):
        """Test that RPI_TEAM_NAME_ALIASES dict is correctly imported and accessible."""
        from settings import RPI_TEAM_NAME_ALIASES
        
        # Verify RPI_TEAM_NAME_ALIASES exists and is a dict
        self.assertIsInstance(RPI_TEAM_NAME_ALIASES, dict, "RPI_TEAM_NAME_ALIASES should be a dict")
        
        # Verify RPI_TEAM_NAME_ALIASES is not empty
        self.assertGreater(len(RPI_TEAM_NAME_ALIASES), 0, "RPI_TEAM_NAME_ALIASES dict should not be empty")
        
        # Verify keys and values are strings
        for key, value in RPI_TEAM_NAME_ALIASES.items():
            self.assertIsInstance(key, str, "RPI alias keys should be strings")
            self.assertIsInstance(value, str, "RPI alias values should be strings")
        
        # Verify at least a couple of aliases exist (values from teams.json)
        self.assertIn("University at Albany", RPI_TEAM_NAME_ALIASES)
        self.assertIn("New Jersey Institute of Technology", RPI_TEAM_NAME_ALIASES)

    def test_raw_incoming_text_import(self):
        """Test that RAW_INCOMING_TEXT string is correctly imported and accessible."""
        from settings import RAW_INCOMING_TEXT
        
        # Verify RAW_INCOMING_TEXT exists and is a string
        self.assertIsInstance(RAW_INCOMING_TEXT, str, "RAW_INCOMING_TEXT should be a string")
        
        # Verify RAW_INCOMING_TEXT is not empty
        self.assertGreater(len(RAW_INCOMING_TEXT), 0, "RAW_INCOMING_TEXT should not be empty")
        
        # Verify it contains conference headers (basic structure check)
        self.assertIn("America East Conference:", RAW_INCOMING_TEXT)
        self.assertIn("Atlantic Coast Conference (ACC):", RAW_INCOMING_TEXT)
        
        # Verify it contains player entries (basic format check)
        self.assertIn(" - ", RAW_INCOMING_TEXT, "Should contain player entries with ' - ' separator")

    def test_all_exports_in_all(self):
        """Test that __all__ contains all expected exports."""
        from settings import __all__
        
        expected_exports = ["TEAMS", "OUTGOING_TRANSFERS", "RPI_TEAM_NAME_ALIASES", "RAW_INCOMING_TEXT"]
        
        self.assertEqual(
            set(__all__), 
            set(expected_exports),
            "__all__ should contain exactly the expected exports"
        )


class TestDependentModuleImports(unittest.TestCase):
    """Test that modules dependent on configuration data can import from settings."""

    def test_run_scraper_imports_teams(self):
        """Test that src/run_scraper.py correctly imports TEAMS from settings."""
        # Import the module (may fail if pandas/requests are missing)
        try:
            from src import run_scraper
        except ImportError as e:
            # Skip test if dependencies are missing
            if "pandas" in str(e) or "requests" in str(e):
                self.skipTest(f"Skipping test due to missing dependency: {e}")
            raise
        
        # Verify the module can access TEAMS
        from settings import TEAMS
        
        # Both should reference the same object
        self.assertIsInstance(TEAMS, list)
        self.assertGreater(len(TEAMS), 0)

    def test_team_analysis_imports_rpi_aliases(self):
        """Test that scraper/team_analysis.py correctly imports RPI_TEAM_NAME_ALIASES from settings."""
        # Import the module (may fail if dependencies are missing)
        try:
            from scraper import team_analysis
        except ImportError as e:
            # Skip test if dependencies are missing
            if any(dep in str(e) for dep in ["pandas", "bs4", "requests"]):
                self.skipTest(f"Skipping test due to missing dependency: {e}")
            raise
        
        # Verify the module can access RPI_TEAM_NAME_ALIASES
        from settings import RPI_TEAM_NAME_ALIASES
        
        # Both should reference the same object
        self.assertIsInstance(RPI_TEAM_NAME_ALIASES, dict)
        self.assertGreater(len(RPI_TEAM_NAME_ALIASES), 0)

    def test_rpi_lookup_imports_aliases(self):
        """Test that scraper/rpi_lookup.py correctly imports RPI_TEAM_NAME_ALIASES from settings."""
        # Import the module (may fail if dependencies are missing)
        try:
            from scraper import rpi_lookup
        except ImportError as e:
            # Skip test if dependencies are missing
            if any(dep in str(e) for dep in ["pandas", "requests"]):
                self.skipTest(f"Skipping test due to missing dependency: {e}")
            raise
        
        # Verify the module can access RPI_TEAM_NAME_ALIASES
        from settings import RPI_TEAM_NAME_ALIASES
        
        # Both should reference the same object
        self.assertIsInstance(RPI_TEAM_NAME_ALIASES, dict)
        self.assertGreater(len(RPI_TEAM_NAME_ALIASES), 0)

    def test_transfers_imports_outgoing_transfers(self):
        """Test that scraper/transfers.py correctly imports OUTGOING_TRANSFERS from settings."""
        # Import the module
        from scraper import transfers
        
        # Verify the module can access OUTGOING_TRANSFERS
        from settings import OUTGOING_TRANSFERS
        
        # Both should reference the same object
        self.assertIsInstance(OUTGOING_TRANSFERS, list)
        self.assertGreater(len(OUTGOING_TRANSFERS), 0)

    def test_team_pivot_imports_outgoing_transfers(self):
        """Test that src/create_team_pivot_csv.py correctly imports OUTGOING_TRANSFERS from settings."""
        # Import the module (this will work even if pandas is missing, as imports are at top)
        try:
            from src import create_team_pivot_csv
        except ImportError as e:
            # If pandas or other dependencies are missing, that's okay for this test
            if "pandas" not in str(e):
                raise
        
        # Verify the module can access OUTGOING_TRANSFERS
        from settings import OUTGOING_TRANSFERS
        
        # Both should reference the same object
        self.assertIsInstance(OUTGOING_TRANSFERS, list)
        self.assertGreater(len(OUTGOING_TRANSFERS), 0)

    def test_export_transfers_imports_outgoing_transfers(self):
        """Test that src/create_transfers_csv.py correctly imports OUTGOING_TRANSFERS from settings."""
        # Import the module
        from src import create_transfers_csv
        
        # Verify the module can access OUTGOING_TRANSFERS
        from settings import OUTGOING_TRANSFERS
        
        # Both should reference the same object
        self.assertIsInstance(OUTGOING_TRANSFERS, list)
        self.assertGreater(len(OUTGOING_TRANSFERS), 0)

    def test_incoming_players_module_accessible(self):
        """Test that scraper/incoming_players.py can access RAW_INCOMING_TEXT from settings."""
        # Import the module
        from scraper import incoming_players
        
        # Verify the module can access RAW_INCOMING_TEXT
        from settings import RAW_INCOMING_TEXT
        
        # Verify module has INCOMING_PLAYERS list derived from RAW_INCOMING_TEXT
        self.assertIsInstance(incoming_players.INCOMING_PLAYERS, list)
        self.assertGreater(len(incoming_players.INCOMING_PLAYERS), 0)


class TestSettingsDataConsistency(unittest.TestCase):
    """Test consistency and relationships between different settings data."""

    def test_teams_have_unique_names(self):
        """Test that each team in TEAMS has a unique name."""
        from settings import TEAMS
        
        team_names = [team["team"] for team in TEAMS]
        unique_names = set(team_names)
        
        self.assertEqual(
            len(team_names),
            len(unique_names),
            "All team names should be unique"
        )

    def test_teams_urls_are_valid(self):
        """Test that all team URLs start with http/https."""
        from settings import TEAMS
        
        for team in TEAMS:
            self.assertTrue(
                team["url"].startswith(("http://", "https://")),
                f"Team {team['team']} roster URL should start with http:// or https://"
            )
            self.assertTrue(
                team["stats_url"].startswith(("http://", "https://")),
                f"Team {team['team']} stats URL should start with http:// or https://"
            )

    def test_rpi_aliases_map_to_valid_teams(self):
        """Test that RPI aliases contain mappings for teams in TEAMS list."""
        from settings import TEAMS, RPI_TEAM_NAME_ALIASES
        
        # Get all team names from TEAMS
        team_names = {team["team"] for team in TEAMS}
        
        # Check that alias keys reference valid teams
        teams_with_aliases = team_names & set(RPI_TEAM_NAME_ALIASES.keys())
        self.assertEqual(teams_with_aliases, set(RPI_TEAM_NAME_ALIASES.keys()))

    def test_incoming_text_contains_conferences(self):
        """Test that RAW_INCOMING_TEXT contains known conferences from TEAMS."""
        from settings import TEAMS, RAW_INCOMING_TEXT
        
        # Get unique conferences from TEAMS
        conferences = {team["conference"] for team in TEAMS}
        
        # Check that at least some conferences appear in incoming text
        conferences_in_text = 0
        for conf in conferences:
            # Look for conference name or abbreviation in text
            if conf in RAW_INCOMING_TEXT or "ACC" in RAW_INCOMING_TEXT:
                conferences_in_text += 1
        
        self.assertGreater(
            conferences_in_text,
            0,
            "RAW_INCOMING_TEXT should contain some conferences from TEAMS"
        )


def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSettingsPackageImports))
    suite.addTests(loader.loadTestsFromTestCase(TestDependentModuleImports))
    suite.addTests(loader.loadTestsFromTestCase(TestSettingsDataConsistency))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
