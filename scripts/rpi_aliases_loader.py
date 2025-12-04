"""RPI aliases now live inside settings/teams.json -> team_name_aliases."""

from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache

DEFAULT_TEAMS_JSON = Path(__file__).resolve().parent.parent / "settings" / "teams.json"


@lru_cache()
def load_rpi_aliases(path: Path | str | None = None):
    p = Path(path) if path else DEFAULT_TEAMS_JSON
    with open(p, "r", encoding="utf-8") as f:
        teams = json.load(f)
    aliases: dict[str, str] = {}
    for t in teams:
        name = t.get("team")
        if not name:
            continue
        for alias in t.get("team_name_aliases", []) or []:
            if alias != name:
                aliases[name] = alias
    return aliases


__all__ = ["load_rpi_aliases", "DEFAULT_TEAMS_JSON"]
