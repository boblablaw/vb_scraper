"""vb_scraper main source package.

Provides small utilities for scripts to ensure the project root is on
``sys.path`` so that imports like ``from scraper.utils import ...`` work
when running modules as plain scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path


def append_project_root() -> None:
    """Ensure the project root directory is on ``sys.path``.

    This lets helper scripts (in ``scripts/``) import the ``scraper`` and
    ``settings`` packages without needing to be executed as ``python -m``.
    """

    root = Path(__file__).resolve().parent.parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
