"""
Pipeline entrypoints for building the Ultimate Guide.

This provides a thin orchestration layer so callers can supply paths/config
without editing the renderer module. For now it reuses the existing PDF renderer
logic; future work can swap renderers or data sources behind the same interface.
"""

from __future__ import annotations

from pathlib import Path

from .models import GuideConfig


def build_pdf(config: GuideConfig | None = None, output_overridden: bool = False):
    """
    Build the guide PDF using the supplied configuration.
    """
    cfg = config or GuideConfig.default()

    # Import late so we can override module-level paths before running main()
    from . import build_ultimate_guide as pdf

    # Override module globals to point at configurable paths
    pdf.TEAM_PIVOT_CSV = Path(cfg.team_pivot_csv)
    pdf.ROSTERS_STATS_CSV = Path(cfg.rosters_stats_csv)
    pdf.LOGOS_DIR = Path(cfg.logos_dir)
    pdf.PNG_DIR = pdf.LOGOS_DIR
    pdf.US_MAP_IMAGE = Path(cfg.us_map_image)
    pdf.OUTPUT_PDF = Path(cfg.output_pdf)
    pdf.OUTPUT_PDF_WAS_OVERRIDDEN = bool(output_overridden)
    pdf.COACHES_CACHE_PATH = Path(cfg.coaches_cache_path)
    pdf.PLAYER_SETTINGS_PATH = Path(cfg.player_settings_path) if cfg.player_settings_path else None

    # Run the existing builder
    pdf.main()


__all__ = ["build_pdf"]
