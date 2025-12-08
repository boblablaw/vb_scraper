import json
from pathlib import Path
from functools import lru_cache

DEFAULT_TRANSFERS_JSON = Path(__file__).resolve().parent.parent / "settings" / "transfers.json"


@lru_cache()
def load_transfers(path: Path | str | None = None):
    p = Path(path) if path else DEFAULT_TRANSFERS_JSON
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = ["load_transfers", "DEFAULT_TRANSFERS_JSON"]
