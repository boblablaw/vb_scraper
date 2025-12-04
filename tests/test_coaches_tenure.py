import pytest

from scraper.coaches import extract_tenure_from_text


@pytest.mark.parametrize(
    "text,current_year,expected_start,expected_seasons",
    [
        (
            "Pendergast enters her third season at Denver in 2025.",
            2025,
            2023,
            3,
        ),
        (
            "Smith was hired in 2019 and has led the Lions ever since.",
            2025,
            2019,
            7,
        ),
        (
            "Jones is in his first year with the program.",
            2025,
            2025,
            1,
        ),
    ],
)
def test_extract_tenure_from_text(text, current_year, expected_start, expected_seasons):
    start_year, seasons = extract_tenure_from_text(text, current_year=current_year)
    assert start_year == expected_start
    assert seasons == expected_seasons
