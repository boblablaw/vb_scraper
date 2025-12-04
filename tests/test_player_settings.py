import importlib
import math

import report_builder.build_ultimate_guide as core
from report_builder.models import PlayerSettings


def test_filter_schools_for_player_restores(monkeypatch):
    original = list(core.SCHOOLS)
    player = PlayerSettings(name="Test Player", schools=[original[0]["name"]])
    try:
        core.filter_schools_for_player(player)
        assert len(core.SCHOOLS) == 1
        assert core.SCHOOLS[0]["name"] == original[0]["name"]
    finally:
        core.SCHOOLS[:] = original


def test_home_coords_override_affects_travel(monkeypatch):
    # Reload core to ensure a clean state for HOME_LAT/HOME_LON
    core_reloaded = importlib.reload(core)
    first_school = core_reloaded.SCHOOLS[0]

    # Set home to the first school's coordinates so distance ~0
    core_reloaded.HOME_LAT = first_school["lat"]
    core_reloaded.HOME_LON = first_school["lon"]
    core_reloaded.compute_travel_and_fit()

    assert math.isclose(first_school["flight_dist_mi"], 0.0, abs_tol=0.1)
    assert math.isclose(first_school["drive_dist_mi"], 0.0, abs_tol=0.2)
