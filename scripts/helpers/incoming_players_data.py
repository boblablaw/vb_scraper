# incoming_players_data.py
"""
Automatic year-based incoming players data selector (now file-based).

Date-based rules for selecting incoming players data:
- Aug 1, 2024 - Jul 31, 2025: Use 2025 data (incoming_players_2025.txt)
- Aug 1, 2025 - Jul 31, 2026: Use 2026 data (incoming_players_2026.txt)
- Aug 1, 2026 - Jul 31, 2027: Use 2027 data (incoming_players_2027.txt)
"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "settings"


def get_incoming_players_year():
    now = datetime.now()
    if now.month >= 8:
        return now.year + 1
    return now.year


def load_incoming_text_for_year(year: int) -> str:
    path = BASE_DIR / f"incoming_players_{year}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # fallback to 2026 file if missing
    fallback = BASE_DIR / "incoming_players_2026.txt"
    return fallback.read_text(encoding="utf-8") if fallback.exists() else ""


def get_raw_incoming_text():
    year = get_incoming_players_year()
    return load_incoming_text_for_year(year)


RAW_INCOMING_TEXT = get_raw_incoming_text()


if __name__ == "__main__":
    year = get_incoming_players_year()
    text = get_raw_incoming_text()
    print(f"Using incoming players data for: {year}")
    print(f"Data length: {len(text)} characters")
