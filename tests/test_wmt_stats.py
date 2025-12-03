import unittest

from scraper.stats import extract_wmt_team_id, parse_wmt_api_players


class TestWmtStatsHelpers(unittest.TestCase):
    def test_extract_wmt_team_id(self):
        self.assertEqual(
            extract_wmt_team_id("https://wmt.games/huskers/stats/season/604893"),
            "604893",
        )
        self.assertEqual(
            extract_wmt_team_id("https://api.wmt.games/api/statistics/teams/12345/players"),
            "12345",
        )
        self.assertIsNone(extract_wmt_team_id("https://example.com/no/team/here"))

    def test_parse_wmt_api_players(self):
        players = [
            {
                "first_name": "Laney",
                "last_name": "Choboy",
                # WMT season stats live under statistic.data.season.columns[].statistic
                "statistic": {
                    "data": {
                        "season": {
                            "gamesPlayed": 2,
                            "gamesStarted": 1,
                            "columns": [
                                {
                                    "period": 0,
                                    "statistic": {
                                        "sKills": 10,
                                        "sAssists": 5,
                                        "sDigs": 20,
                                        "sBlockAssists": 4,
                                        "sBlockSolos": 2,
                                        "sErrors": 3,
                                        "sTotalAttacks": 50,
                                        "sAttackPCT": 0.234,
                                        "sPoints": 30,
                                        "sAces": 3,
                                        "sAcesPerGame": 0.5,
                                        "sServiceErrors": 1,
                                        "sDigsPerGame": 4.0,
                                        "sAssistsPerGame": 1.0,
                                        "sKillsPerGame": 2.0,
                                        "sTotalBlocks": 6,
                                        "sTotalBlocksPerGame": 1.2,
                                        "sSets": 15,
                                        "sReturnErrors": 1,
                                        "sReturnAttempts": 40,
                                        "sBallHandlingErrors": 2,
                                    },
                                }
                            ],
                        }
                    }
                },
                "games": [{"gamesStarted": 1}, {"gamesStarted": 0}],
            }
        ]

        df = parse_wmt_api_players(players)
        self.assertIsNotNone(df)
        row = df.iloc[0].to_dict()

        self.assertEqual(row["player"], "Laney Choboy")
        self.assertEqual(row["matches_played"], 2)
        self.assertEqual(row["matches_started"], 1)
        self.assertEqual(row["sets_played"], 15)
        self.assertEqual(row["kills"], 10)
        self.assertEqual(row["assists"], 5)
        self.assertAlmostEqual(row["kills_per_set"], 2.0)
        self.assertAlmostEqual(row["assists_per_set"], 1.0)
        self.assertEqual(row["total_blocks"], 6)
        self.assertAlmostEqual(row["blocks_per_set"], 1.2)
        self.assertAlmostEqual(row["reception_pct"], (40 - 1) / 40)


if __name__ == "__main__":
    unittest.main()
