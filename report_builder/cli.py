#!/usr/bin/env python3
"""
CLI wrapper for building the Ultimate Guide.

Usage:
    python -m report_builder.cli                      # build with defaults
    python -m report_builder.cli --output exports/guide.pdf
    python -m report_builder.cli --team-pivot path/to/team_pivot.csv --rosters path/to/rosters_and_stats.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .models import GuideConfig
from .pipelines import build_pdf


def parse_args():
    p = argparse.ArgumentParser(description="Build the Ultimate Guide PDF")
    p.add_argument("--team-pivot", dest="team_pivot_csv", type=Path)
    p.add_argument("--rosters", dest="rosters_stats_csv", type=Path)
    p.add_argument("--logos-dir", dest="logos_dir", type=Path)
    p.add_argument("--output", dest="output_pdf", type=Path)
    p.add_argument("--us-map", dest="us_map_image", type=Path)
    p.add_argument("--coaches-cache", dest="coaches_cache_path", type=Path)
    p.add_argument("--player-settings", dest="player_settings_path", type=Path)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = GuideConfig.default()

    output_overridden = False
    if args.team_pivot_csv:
        cfg.team_pivot_csv = args.team_pivot_csv
    if args.rosters_stats_csv:
        cfg.rosters_stats_csv = args.rosters_stats_csv
    if args.logos_dir:
        cfg.logos_dir = args.logos_dir
    if args.output_pdf:
        cfg.output_pdf = args.output_pdf
        output_overridden = True
    if args.us_map_image:
        cfg.us_map_image = args.us_map_image
    if args.coaches_cache_path:
        cfg.coaches_cache_path = args.coaches_cache_path
    if args.player_settings_path:
        cfg.player_settings_path = args.player_settings_path

    build_pdf(cfg, output_overridden=output_overridden)


if __name__ == "__main__":
    main()
