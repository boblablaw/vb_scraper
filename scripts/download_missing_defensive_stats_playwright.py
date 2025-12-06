#!/usr/bin/env python3
"""
Scrape offensive and defensive stats tables for teams missing defensive stats using Playwright.

The script:
- Finds the latest validation/reports/missing_defensive_stats_*.txt (or a provided report)
- Resolves team names to stats_url entries in settings/teams.json (aliases included)
- Visits each stats_url, scrapes the visible table as CSV (default Offensive), switches the dropdown to Defensive, and scrapes again
- Saves files under stats/playwright_downloads/<team>_{offensive|defensive}.csv

Usage:
    python scripts/download_missing_defensive_stats_playwright.py
    python scripts/download_missing_defensive_stats_playwright.py --headed --limit 5
    python scripts/download_missing_defensive_stats_playwright.py --team \"Baylor University\" --team \"Rice University\"

Requires:
    pip install -r requirements-browser.txt
    playwright install chromium
"""

import argparse
import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

try:
    from playwright.async_api import (
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
except ImportError as exc:  # pragma: no cover - import guard for optional dependency
    raise SystemExit(
        "Playwright is required. Install with `pip install playwright` then run "
        "`playwright install chromium`."
    ) from exc


ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "validation" / "reports"
TEAMS_PATH = ROOT_DIR / "settings" / "teams.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "stats" / "playwright_downloads"

REPORT_PREFIX = "missing_defensive_stats_"

# Table selector we expect on stats pages.
TABLE_SELECTOR = "table"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape offensive/defensive stats tables for missing teams via Playwright."
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Path to a specific missing_defensive_stats report (defaults to latest).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Where to save CSVs (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N teams from the report.",
    )
    parser.add_argument(
        "--team",
        action="append",
        help="Process only the given team name(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (default is headless).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=35,
        help="Per-action timeout in seconds (default: 35).",
    )
    return parser.parse_args()


def find_latest_report() -> Path:
    candidates = sorted(REPORTS_DIR.glob(f"{REPORT_PREFIX}*.txt"))
    if not candidates:
        raise FileNotFoundError(f"No report found in {REPORTS_DIR}")

    def report_key(path: Path) -> datetime:
        parts = path.stem.split("_")
        try:
            # missing_defensive_stats_YYYYMMDD_HHMMSS
            return datetime.strptime("_".join(parts[-2:]), "%Y%m%d_%H%M%S")
        except Exception:
            return datetime.fromtimestamp(path.stat().st_mtime)

    return max(candidates, key=report_key)


def parse_team_names(report_path: Path) -> List[str]:
    lines = report_path.read_text(encoding="utf-8").splitlines()
    teams = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    return teams


def load_teams(path: Path = TEAMS_PATH) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_team_lookup(teams: Sequence[Dict]) -> Dict[str, Dict]:
    lookup: Dict[str, Dict] = {}
    for team in teams:
        names: List[str] = [team.get("team", "")]
        names.extend(team.get("team_name_aliases") or [])
        names.append(team.get("short_name") or "")
        for name in names:
            if not name:
                continue
            lookup[name.casefold()] = team
    return lookup


def slugify_team(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return safe or "team"


async def click_dropdown_option(page, option_text: str, timeout_ms: int) -> None:
    """
    Open the stats view dropdown (Offensive/Defensive) and select the given option.
    """
    toggle_candidates = [
        page.locator(".s-select__selected-option").filter(has_text=re.compile("Offensive|Defensive", re.I)),
        page.locator("[data-test-id='s-select__selected-option']").filter(has_text=re.compile("Offensive|Defensive", re.I)),
        page.locator(".s-select__selected-option"),
    ]
    toggle = None
    for cand in toggle_candidates:
        if await cand.count():
            toggle = cand.first
            break
    if not toggle:
        raise RuntimeError("Could not find stats view dropdown")

    await toggle.click()
    await page.wait_for_timeout(250)

    options = page.locator(".s-select__option-item")
    if await options.count() == 0:
        options = page.locator("[data-test-id='s-select__option-item']")

    target = options.filter(has_text=re.compile(option_text, re.I))
    if await target.count() == 0:
        target = page.get_by_text(option_text, exact=False)

    await target.first.wait_for(state="visible", timeout=timeout_ms)
    await target.first.click()
    await page.wait_for_timeout(500)
    # Avoid waiting indefinitely on sites with streaming network requests.
    await page.wait_for_load_state("domcontentloaded")


async def ensure_view(page, view_text: str, timeout_ms: int) -> None:
    """Switch to the desired view if not already selected."""
    try:
        current = await page.locator(".s-select__selected-option__text").first.inner_text()
    except Exception:
        current = ""
    if view_text.lower() in current.lower():
        return
    await click_dropdown_option(page, view_text, timeout_ms)


async def extract_table(page) -> tuple[list[list[str]], list[list[str]]]:
    table = await page.query_selector(TABLE_SELECTOR)
    if not table:
        raise RuntimeError("No table found on page")

    data = await table.evaluate(
        """(table) => {
            const headerRows = Array.from(table.querySelectorAll('thead tr')).map(row =>
                Array.from(row.cells).map(c => c.innerText.trim())
            );
            const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                Array.from(tr.querySelectorAll('th, td')).map(td => td.innerText.trim())
            );
            return { headerRows, rows };
        }"""
    )
    return data.get("headerRows", []), data.get("rows", [])


def normalize_headers(headers: list[str]) -> list[str]:
    normalized = []
    for idx, h in enumerate(headers):
        normalized.append(h if h.strip() else f"col{idx+1}")
    if not normalized:
        normalized = []
    return normalized


def select_headers(header_rows: list[list[str]], body_rows: list[list[str]]) -> list[str]:
    if not header_rows:
        return []

    target_len = len(body_rows[0]) if body_rows else len(header_rows[-1])
    best = header_rows[-1]

    for row in header_rows:
        if target_len and len(row) == target_len:
            best = row
        elif len(row) > len(best):
            best = row

    return normalize_headers(best)


def write_csv(headers: list[str], rows: list[list[str]], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        writer.writerows(rows)
    return destination


async def process_team(page, team_entry: Dict, output_dir: Path, timeout_ms: int) -> Dict[str, Optional[Path]]:
    team_name = team_entry["team"]
    stats_url = team_entry.get("stats_url")
    slug = slugify_team(team_name)
    results: Dict[str, Optional[Path]] = {"offensive": None, "defensive": None}

    if not stats_url:
        print(f"[SKIP] {team_name}: no stats_url")
        return results

    print(f"[VISIT] {team_name}: {stats_url}")
    try:
        await page.goto(stats_url, wait_until="domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print(f"[ERROR] {team_name}: page load timed out")
        return results

    try:
        await page.wait_for_selector(TABLE_SELECTOR, timeout=timeout_ms)
    except PlaywrightTimeoutError:
        print(f"[ERROR] {team_name}: table not found after load")
        return results

    await page.wait_for_timeout(800)

    offensive_path = output_dir / f"{slug}_offensive.csv"
    try:
        await ensure_view(page, "Offensive", timeout_ms)
        header_rows, rows = await extract_table(page)
        headers = select_headers(header_rows, rows)
        results["offensive"] = write_csv(headers, rows, offensive_path)
        print(f"[OK] {team_name}: offensive -> {offensive_path.name}")
    except Exception as exc:
        print(f"[ERROR] {team_name}: offensive scrape failed ({exc})")

    try:
        await ensure_view(page, "Defensive", timeout_ms)
        await page.wait_for_timeout(800)
        header_rows, rows = await extract_table(page)
        headers = select_headers(header_rows, rows)
        defensive_path = output_dir / f"{slug}_defensive.csv"
        results["defensive"] = write_csv(headers, rows, defensive_path)
        print(f"[OK] {team_name}: defensive -> {defensive_path.name}")
    except Exception as exc:
        print(f"[ERROR] {team_name}: defensive scrape failed ({exc})")

    return results


def filter_teams(target_names: Iterable[str], lookup: Dict[str, Dict]) -> tuple[List[Dict], List[str]]:
    resolved = []
    missing: List[str] = []
    for name in target_names:
        match = lookup.get(name.casefold())
        if match:
            resolved.append(match)
        else:
            missing.append(name)
    return resolved, missing


async def main() -> None:
    args = parse_args()
    report_path = args.report or find_latest_report()
    timeout_ms = int(args.timeout * 1000)

    teams_in_report = parse_team_names(report_path)
    if args.team:
        # Preserve order while filtering to requested teams.
        targets = [name for name in teams_in_report if name in set(args.team)]
    else:
        targets = teams_in_report

    if args.limit:
        targets = targets[: args.limit]

    teams_data = load_teams()
    lookup = build_team_lookup(teams_data)
    resolved, missing = filter_teams(targets, lookup)

    if missing:
        print(f"[WARN] {len(missing)} teams not found in teams.json:")
        for name in missing:
            print(f"       - {name}")

    if not resolved:
        print("No teams to process.")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Using report: {report_path.name}")
    print(f"[INFO] Saving CSVs to: {args.output_dir}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        context = await browser.new_context(accept_downloads=True)
        context.set_default_timeout(timeout_ms)
        page = await context.new_page()

        for team_entry in resolved:
            await process_team(page, team_entry, args.output_dir, timeout_ms)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
