import json
from pathlib import Path
from functools import lru_cache

DEFAULT_TEAMS_JSON = Path(__file__).resolve().parent.parent / "settings" / "teams.json"


@lru_cache()
def load_teams(path: Path | str | None = None):
    """
    Load teams list from JSON. Cached for repeated callers.
    """
    p = Path(path) if path else DEFAULT_TEAMS_JSON
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = ["load_teams", "DEFAULT_TEAMS_JSON"]
