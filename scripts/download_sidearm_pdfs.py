import argparse
import csv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

# Add project root to path so we can import the settings package
sys.path.insert(0, str(Path(__file__).parent.parent))

from settings.teams import TEAMS
from settings.teams_urls import get_season_year


S3_TEMPLATE = "https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/{domain}/stats/wvball/{year}/pdf/cume.pdf"


def extract_domain(url: str | None) -> str | None:
    """Extract bare domain (netloc) from a URL.

    Examples:
        https://miamiredhawks.com/sports/... -> miamiredhawks.com
        https://www.kstatesports.com/...    -> kstatesports.com
    """
    if not url:
        return None

    parsed = urlparse(url)
    netloc = parsed.netloc
    if not netloc:
        return None

    # Strip common prefixes like www.
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc


def build_pdf_url(team: dict, year: int) -> tuple[str | None, str | None]:
    """Build the Sidearm S3 PDF URL for a team, if possible.

    Returns (pdf_url, domain) or (None, None) if a domain cannot be determined.
    """
    stats_url = team.get("stats_url")
    roster_url = team.get("url")

    domain = extract_domain(stats_url) or extract_domain(roster_url)
    if not domain:
        return None, None

    pdf_url = S3_TEMPLATE.format(domain=domain, year=year)
    return pdf_url, domain


def download_pdfs(year: int | None = None,
                  output_dir: str = "exports/sidearm_pdfs",
                  overwrite: bool = False,
                  timeout: int = 10) -> None:
    """Attempt to download cumulative stats PDFs for all teams.

    For each team in TEAMS, we:
      * derive the domain from its stats/roster URL
      * build the Sidearm S3 cume.pdf URL for the given year
      * if the PDF exists (HTTP 200), save it under output_dir

    Non-Sidearm teams (or teams without that S3 path) will simply log a miss.
    """
    if year is None:
        year = get_season_year()

    os.makedirs(output_dir, exist_ok=True)

    print(f"Using season year: {year}")
    print(f"Saving PDFs to: {output_dir}")

    for team in TEAMS:
        team_name = team.get("team", "<unknown>")
        pdf_url, domain = build_pdf_url(team, year)
        if not pdf_url or not domain:
            print(f"[SKIP] {team_name}: could not determine domain from URLs")
            continue

        safe_domain = domain.replace("/", "_")
        filename = f"{safe_domain}_cume_{year}.pdf"
        out_path = os.path.join(output_dir, filename)

        if not overwrite and os.path.exists(out_path):
            print(f"[SKIP] {team_name}: file already exists at {out_path}")
            continue

        try:
            resp = requests.get(pdf_url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {team_name}: request failed for {pdf_url} -> {exc}")
            continue

        if resp.status_code == 200 and "application/pdf" in resp.headers.get("Content-Type", "").lower():
            with open(out_path, "wb") as f:
                f.write(resp.content)
            print(f"[OK] {team_name}: downloaded to {out_path}")
        else:
            print(
                f"[MISS] {team_name}: no PDF at {pdf_url} "
                f"(status={resp.status_code}, content-type={resp.headers.get('Content-Type')})"
            )


def generate_report(year: int | None = None,
                    output_dir: str = "exports/sidearm_pdfs",
                    report_filename: str | None = None) -> str:
    """Generate a CSV report of which teams have PDFs downloaded.

    The report has one row per team with columns:
        team, conference, domain, pdf_filename, has_pdf

    Returns the path to the report file.
    """
    if year is None:
        year = get_season_year()

    os.makedirs(output_dir, exist_ok=True)

    if report_filename is None:
        report_filename = os.path.join(output_dir, f"sidearm_pdfs_coverage_{year}.csv")

    rows = []

    for team in TEAMS:
        team_name = team.get("team", "<unknown>")
        conference = team.get("conference", "")
        _pdf_url, domain = build_pdf_url(team, year)

        if not domain:
            domain = ""
            pdf_filename = ""
            has_pdf = False
        else:
            safe_domain = domain.replace("/", "_")
            pdf_filename = f"{safe_domain}_cume_{year}.pdf"
            out_path = os.path.join(output_dir, pdf_filename)
            has_pdf = os.path.exists(out_path)

        rows.append(
            {
                "team": team_name,
                "conference": conference,
                "domain": domain,
                "pdf_filename": pdf_filename,
                "has_pdf": has_pdf,
            }
        )

    fieldnames = ["team", "conference", "domain", "pdf_filename", "has_pdf"]
    with open(report_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Coverage report written to: {report_filename}")
    return report_filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download Sidearm cumulative stats PDFs (cume.pdf) from the "
            "Sidearm S3 bucket for each team defined in settings/teams.py."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help=(
            "Season year used in the S3 path (e.g. 2025). If omitted, "
            "uses settings.teams_urls.get_season_year()."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="exports/sidearm_pdfs",
        help="Directory to write downloaded PDFs (default: exports/sidearm_pdfs)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files if they already exist.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help=(
            "Only generate a coverage report based on existing PDFs; "
            "do not attempt any downloads."
        ),
    )

    args = parser.parse_args()

    if args.report_only:
        generate_report(year=args.year, output_dir=args.output_dir)
        return

    download_pdfs(
        year=args.year,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        timeout=args.timeout,
    )

    # After downloading, also write a coverage report for convenience
    generate_report(year=args.year, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
