from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


def _default_db_url() -> str:
    root = Path(__file__).resolve().parents[2]
    db_path = root / "data" / "vb.db"
    return f"sqlite:///{db_path}"


class Settings(BaseModel):
    db_url: str = Field(default_factory=_default_db_url)
    api_title: str = "VB Scraper API"
    api_description: str = "FastAPI backend exposing rosters, stats, and school metadata."
    api_version: str = "0.1.0"


@lru_cache()
def get_settings() -> Settings:
    return Settings(db_url=os.getenv("VB_DB_URL", _default_db_url()))
