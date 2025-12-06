from __future__ import annotations

import logging
import os
from typing import Optional

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    sync_playwright = None
    PlaywrightTimeoutError = None

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    val = os.environ.get(name)
    return bool(val and val.strip().lower() in {"1", "true", "yes", "y"})


def _env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    val = os.environ.get(name)
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        logger.warning("Ignoring invalid integer for %s=%r", name, val)
        return default


_PLAYWRIGHT_TIMEOUT_CONFIG = _env_int("VB_PLAYWRIGHT_PROFILE_FETCH_TIMEOUT_MS", 30000)
PLAYWRIGHT_PROFILE_FETCH_TIMEOUT_MS = (
    _PLAYWRIGHT_TIMEOUT_CONFIG if _PLAYWRIGHT_TIMEOUT_CONFIG is not None else 30000
)
PLAYWRIGHT_PROFILE_FETCH_LIMIT = _env_int("VB_PLAYWRIGHT_PROFILE_FETCH_LIMIT")
PLAYWRIGHT_ENABLED = bool(sync_playwright) and not _env_flag("VB_DISABLE_PLAYWRIGHT")
_PLAYWRIGHT_FETCH_COUNT = 0


def should_use_playwright() -> bool:
    if not PLAYWRIGHT_ENABLED:
        return False
    limit = PLAYWRIGHT_PROFILE_FETCH_LIMIT
    if limit is None:
        return True
    return _PLAYWRIGHT_FETCH_COUNT < limit


def record_playwright_use() -> None:
    global _PLAYWRIGHT_FETCH_COUNT
    _PLAYWRIGHT_FETCH_COUNT += 1
