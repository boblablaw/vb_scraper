import importlib

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Table

import report_builder.build_ultimate_guide as core
from report_builder.renderers import sections


@pytest.fixture
def sample_schools(monkeypatch):
    original = list(core.SCHOOLS)
    sample = [
        {
            "name": "Alpha University",
            "short": "Alpha",
            "travel_difficulty": 40,
            "drive_dist_mi": 200,
            "drive_time_hr": 3.3,
            "flight_dist_mi": 300,
            "flight_time_hr": 0.9,
            "fit_score": 2.0,
            "conference": "Test",
            "tier": "A",
            "offense_type": "5-1",
            "city_state": "Alpha City, AA",
            "rpi_rank": 100,
            "record": "10-10",
            "politics_label": "",
            "notes": "",
            "roster_2026": [],
            "coaches": [],
            "vb_opp_score": 2.5,
            "geo_score": 2.0,
            "academic_score": 3.0,
        },
        {
            "name": "Beta College",
            "short": "Beta",
            "travel_difficulty": 10,
            "drive_dist_mi": 50,
            "drive_time_hr": 0.8,
            "flight_dist_mi": 70,
            "flight_time_hr": 0.2,
            "fit_score": 2.9,
            "conference": "Test",
            "tier": "B+",
            "offense_type": "5-1",
            "city_state": "Beta Town, BB",
            "rpi_rank": 50,
            "record": "12-5",
            "politics_label": "",
            "notes": "",
            "roster_2026": [],
            "coaches": [],
            "vb_opp_score": 2.8,
            "geo_score": 2.5,
            "academic_score": 2.7,
        },
        {
            "name": "Gamma Institute",
            "short": "Gamma",
            "travel_difficulty": 25,
            "drive_dist_mi": 120,
            "drive_time_hr": 2.0,
            "flight_dist_mi": 180,
            "flight_time_hr": 0.5,
            "fit_score": 2.3,
            "conference": "Test",
            "tier": "B",
            "offense_type": "6-2",
            "city_state": "Gamma, CC",
            "rpi_rank": 75,
            "record": "9-11",
            "politics_label": "",
            "notes": "",
            "roster_2026": [],
            "coaches": [],
            "vb_opp_score": 2.6,
            "geo_score": 2.1,
            "academic_score": 2.3,
        },
    ]
    monkeypatch.setattr(core, "SCHOOLS", sample)
    yield sample
    core.SCHOOLS[:] = original


def _first_table(story):
    for item in story:
        if isinstance(item, Table):
            return item
    return None


def _school_heading_order(story, names_set):
    seen = []
    for item in story:
        if isinstance(item, Paragraph):
            text = item.text
            if text in names_set and text not in seen:
                seen.append(text)
    return seen


def test_travel_snapshot_sorted_by_difficulty(sample_schools, monkeypatch):
    styles = getSampleStyleSheet()
    story = []
    sections.build_travel_matrix(core, story, styles)
    table = _first_table(story)
    assert table is not None
    rows = table._cellvalues[1:]  # skip header
    order = [row[0] for row in rows]
    # Expect Beta (10) -> Gamma (25) -> Alpha (40)
    assert order == ["Beta", "Gamma", "Alpha"]


def test_school_pages_sorted_by_fit_score(sample_schools, monkeypatch):
    styles = getSampleStyleSheet()
    story = []
    sections.build_school_pages(core, story, styles)
    order = _school_heading_order(story, {s["name"] for s in sample_schools})
    # Expect Beta (2.9) -> Gamma (2.3) -> Alpha (2.0)
    assert order[:3] == ["Beta College", "Gamma Institute", "Alpha University"]
