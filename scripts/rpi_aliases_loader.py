import json
from pathlib import Path
from functools import lru_cache

DEFAULT_RPI_ALIASES_JSON = Path(__file__).resolve().parent.parent / "settings" / "rpi_team_name_aliases.json"


@lru_cache()
def load_rpi_aliases(path: Path | str | None = None):
    p = Path(path) if path else DEFAULT_RPI_ALIASES_JSON
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = ["load_rpi_aliases", "DEFAULT_RPI_ALIASES_JSON"]
