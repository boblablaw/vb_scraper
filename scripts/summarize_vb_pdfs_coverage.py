#!/usr/bin/env python3
"""Summarize volleyball PDF coverage per team.

Merges:
- Sidearm cume PDF coverage from download_sidearm_pdfs.py
- Alternate VB stats PDFs from find_vb_stats_pdfs.py

into a single CSV with one row per team.
"""

import argparse
import csv
import os


DEFAULT_SIDEARM_COVERAGE = "exports/sidearm_pdfs/sidearm_pdfs_coverage_{year}.csv"
DEFAULT_VB_REPORT = "exports/vb_stats_pdfs/vb_stats_pdfs_report_{year}.csv"
DEFAULT_OUTPUT = "exports/sidearm_pdfs/sidearm_pdfs_combined_{year}.csv"


def load_csv_by_team(path: str, key_field: str = "team") -> dict:
    """Load a CSV into a dict keyed by team name."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")

    data: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = (row.get(key_field) or "").strip()
            if not team:
                continue
            data[team] = row
    return data


def summarize(year: int,
              sidearm_csv: str,
              vb_report_csv: str,
              output_csv: str) -> str:
    """Merge coverage and VB-stats reports into a single CSV.

    Output columns:
      team,
      conference,
      domain,
      sidearm_pdf_filename,
      sidearm_has_pdf,
      vb_stats_pdf_filename,
      vb_stats_url,
      stats_url,
      vb_status
    """
    sidearm = load_csv_by_team(sidearm_csv)
    vb = load_csv_by_team(vb_report_csv)

    # Union of all team names from both inputs
    all_teams = sorted(set(sidearm.keys()) | set(vb.keys()))

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)

    fieldnames = [
        "team",
        "conference",
        "domain",
        "sidearm_pdf_filename",
        "sidearm_has_pdf",
        "vb_stats_pdf_filename",
        "vb_stats_url",
        "stats_url",
        "vb_status",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for team in all_teams:
            s_row = sidearm.get(team, {})
            v_row = vb.get(team, {})

            # Prefer conference from Sidearm; fall back to VB report
            conference = (s_row.get("conference") or v_row.get("conference") or "").strip()

            # domain/filename/has_pdf from Sidearm coverage
            domain = (s_row.get("domain") or "").strip()
            sidearm_pdf_filename = (s_row.get("pdf_filename") or "").strip()
            sidearm_has_pdf = (s_row.get("has_pdf") or "").strip()

            # VB stats info
            vb_stats_pdf_filename = (v_row.get("local_filename") or "").strip()
            vb_stats_url = (v_row.get("found_pdf_url") or "").strip()
            stats_url = (v_row.get("stats_url") or "").strip()
            vb_status = (v_row.get("status") or "").strip()

            writer.writerow(
                {
                    "team": team,
                    "conference": conference,
                    "domain": domain,
                    "sidearm_pdf_filename": sidearm_pdf_filename,
                    "sidearm_has_pdf": sidearm_has_pdf,
                    "vb_stats_pdf_filename": vb_stats_pdf_filename,
                    "vb_stats_url": vb_stats_url,
                    "stats_url": stats_url,
                    "vb_status": vb_status,
                }
            )

    print(f"Combined summary written to: {output_csv}")
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge Sidearm cume PDF coverage and alternate VB stats PDFs "
            "into a single per-team summary CSV."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Season year to summarize (e.g., 2025)",
    )
    parser.add_argument(
        "--sidearm-coverage",
        default=None,
        help=(
            "Path to Sidearm coverage CSV. "
            "Default: exports/sidearm_pdfs/sidearm_pdfs_coverage_{year}.csv"
        ),
    )
    parser.add_argument(
        "--vb-report",
        default=None,
        help=(
            "Path to VB stats report CSV. "
            "Default: exports/vb_stats_pdfs/vb_stats_pdfs_report_{year}.csv"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output CSV path. "
            "Default: exports/sidearm_pdfs/sidearm_pdfs_combined_{year}.csv"
        ),
    )

    args = parser.parse_args()

    year = args.year
    sidearm_csv = args.sidearm_coverage or DEFAULT_SIDEARM_COVERAGE.format(year=year)
    vb_report_csv = args.vb_report or DEFAULT_VB_REPORT.format(year=year)
    output_csv = args.output or DEFAULT_OUTPUT.format(year=year)

    summarize(year, sidearm_csv, vb_report_csv, output_csv)


if __name__ == "__main__":
    main()
