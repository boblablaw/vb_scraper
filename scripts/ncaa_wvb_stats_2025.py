import atexit
import random
import time
from typing import Optional, List

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeoutError,
        sync_playwright,
    )
except ImportError:  # pragma: no cover - optional dependency
    sync_playwright = None  # type: ignore
    PlaywrightTimeoutError = Exception  # type: ignore


# --------- CONFIG ---------

TEAMS_JSON = Path(__file__).resolve().parent.parent / "settings" / "teams.json"
REQUEST_SLEEP = 1.0              # seconds between requests to avoid hammering
TIMEOUT = 30                     # request timeout in seconds
HUMAN_DELAY_RANGE = (1.0, 3.0)    # extra jitter before each page fetch
HEADLESS = True                  # toggle to False for debugging
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)
REQUEST_USER_AGENT = USER_AGENT
COOKIE_STR = ""
COOKIE_FILE: Path | None = None
USE_PLAYWRIGHT = True            # can be disabled via CLI
REQUESTS_MAX_RPS = 4.0           # when not using Playwright, cap to 4 req/sec

_PLAYWRIGHT = None
_BROWSER = None
_PAGE = None
_LAST_HTTP_TS = 0.0


def _ensure_playwright_page():
    """
    Lazily start a single Playwright page we can reuse across requests.
    Falls back to requests if Playwright is not installed.
    """
    if not USE_PLAYWRIGHT:
        return None
    global _PLAYWRIGHT, _BROWSER, _PAGE
    if not sync_playwright:
        return None
    if _PAGE:
        return _PAGE
    _PLAYWRIGHT = sync_playwright().start()
    _BROWSER = _PLAYWRIGHT.chromium.launch(headless=HEADLESS)
    extra_headers = {
        "User-Agent": REQUEST_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    cookie_header = COOKIE_STR or (
        COOKIE_FILE.read_text(encoding="utf-8").strip() if COOKIE_FILE and COOKIE_FILE.exists() else ""
    )
    if cookie_header:
        extra_headers["Cookie"] = cookie_header
    context = _BROWSER.new_context(user_agent=REQUEST_USER_AGENT, extra_http_headers=extra_headers)
    _PAGE = context.new_page()
    return _PAGE


def _shutdown_playwright():
    global _PLAYWRIGHT, _BROWSER, _PAGE
    try:
        if _PAGE:
            _PAGE.context.close()
        if _BROWSER:
            _BROWSER.close()
        if _PLAYWRIGHT:
            _PLAYWRIGHT.stop()
    except Exception:
        pass
    finally:
        _PAGE = None
        _BROWSER = None
        _PLAYWRIGHT = None


atexit.register(_shutdown_playwright)


def _human_pause() -> None:
    """Sleep a random amount to mimic human navigation cadence."""
    low, high = HUMAN_DELAY_RANGE
    time.sleep(random.uniform(low, high))


def _rate_limit_requests() -> None:
    """Enforce a max requests/sec when using plain HTTP (no Playwright)."""
    global _LAST_HTTP_TS
    min_interval = 1.0 / REQUESTS_MAX_RPS
    now = time.monotonic()
    delta = now - _LAST_HTTP_TS
    if delta < min_interval:
        time.sleep(min_interval - delta)
    _LAST_HTTP_TS = time.monotonic()


def load_wvb_teams(year: int) -> pd.DataFrame:
    """
    Load team metadata from settings/teams.json using ncaa_stats.2025.team_id.
    Returns DataFrame with columns: team_id, team_name, conference, div, yr.
    """
    if not TEAMS_JSON.exists():
        raise FileNotFoundError(f"Missing teams.json at {TEAMS_JSON}")
    teams = json.loads(TEAMS_JSON.read_text())
    records = []
    for entry in teams:
        tid = entry.get("ncaa_stats", {}).get(str(year), {}).get("team_id")
        if not tid:
            continue
        records.append(
            {
                "team_id": str(tid),
                "team_name": entry.get("team") or entry.get("short_name") or "",
                "conference": entry.get("conference", ""),
                "div": 1,
                "yr": year,
            }
        )
    if not records:
        raise RuntimeError("No teams with ncaa_stats team_id found in teams.json")
    df = pd.DataFrame(records)
    return df


def find_team_id(
    teams_df: pd.DataFrame,
    team_name: str,
    year: int,
) -> str:
    """
    Rough Python equivalent of ncaavolleyballr::find_team_id().

    First tries exact match on team_name; if none, tries a contains search.
    Returns a single team_id or raises ValueError if ambiguous or not found.
    """
    # Exact match on team_name and year
    mask = (teams_df["team_name"] == team_name) & (teams_df["yr"] == year)
    matches = teams_df[mask]

    if matches.empty:
        # Try a contains search as a fallback (case-insensitive)
        mask2 = teams_df["team_name"].str.contains(
            team_name, case=False, na=False
        ) & (teams_df["yr"] == year)
        matches = teams_df[mask2]

    if matches.empty:
        raise ValueError(f"No team_id found for team={team_name!r}, year={year}")
    if len(matches) > 1:
        raise ValueError(
            f"Multiple team_ids found for team={team_name!r}, year={year}. "
            f"Matches: {matches[['team_name','yr','team_id']].to_dict(orient='records')}"
        )

    return str(matches.iloc[0]["team_id"])


def _get_html(url: str) -> str:
    """
    Fetch a page using Playwright to mimic a real browser (bypasses stats.ncaa.org
    automation blocks). Falls back to requests if Playwright is unavailable.
    """
    if USE_PLAYWRIGHT:
        _human_pause()
        page = _ensure_playwright_page()
        if page:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=TIMEOUT * 1000)
                except PlaywrightTimeoutError:
                    pass
                # Wait for a stats table to render; NCAA pages can be slow.
                try:
                    page.wait_for_selector('table:has-text("Player")', timeout=TIMEOUT * 1000)
                except PlaywrightTimeoutError:
                    try:
                        page.wait_for_selector("table", timeout=TIMEOUT * 1000)
                    except PlaywrightTimeoutError:
                        pass
                page.wait_for_timeout(500)
                return page.content()
            except PlaywrightTimeoutError as e:
                print(f"[WARN] Playwright timeout for {url}: {e}")
            except Exception as e:
                print(f"[WARN] Playwright fetch failed for {url}: {e}")

    # Fallback: simple HTTP GET (rate-limited)
    _rate_limit_requests()
    headers = {
        "User-Agent": REQUEST_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    cookie_header = COOKIE_STR or (
        COOKIE_FILE.read_text(encoding="utf-8").strip() if COOKIE_FILE and COOKIE_FILE.exists() else ""
    )
    if cookie_header:
        headers["Cookie"] = cookie_header
    resp = requests.get(url, timeout=TIMEOUT, headers=headers)
    resp.raise_for_status()
    return resp.text


def _extract_player_table_from_html(html: str) -> pd.DataFrame:
    """
    Find the table that has a 'Player' column. This mirrors the R code that
    selects the second table on the page, but is a bit more robust.
    """
    tables = pd.read_html(StringIO(html))
    for t in tables:
        if "Player" in t.columns:
            if not t.empty:
                # If pandas parsed it, also attempt to extract PlayerID if present.
                if "PlayerID" not in t.columns:
                    t = _inject_player_ids_from_links(t, html)
                return t
            # If the table exists but is empty, fall through to manual parsing.

    # Fallback: parse manually in case pandas misses it or returns empty
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        raise ValueError("No table with a 'Player' column found on page.")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="stat_grid") or soup.find("table")
    if not table:
        raise ValueError("No table with a 'Player' column found on page.")

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    # Insert PlayerID column immediately before Player if present
    if "Player" in headers:
        player_idx = headers.index("Player")
        headers.insert(player_idx, "PlayerID")

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        row = []
        for td in cells:
            # If this cell is the Player cell, extract the ID from the link
            link = td.find("a")
            if link and link.get("href", "").startswith("/players/"):
                href = link["href"]
                player_id = href.rstrip("/").split("/")[-1]
                row.append(player_id)
                row.append(link.get_text(strip=True))
            else:
                row.append(td.get_text(strip=True))
        rows.append(row)

    if not rows or "Player" not in headers:
        raise ValueError("No table with a 'Player' column found on page.")

    df = pd.DataFrame(rows, columns=headers[: len(rows[0])])
    return df


def _inject_player_ids_from_links(df: pd.DataFrame, html: str) -> pd.DataFrame:
    """
    If the HTML contains player links (/players/<id>), inject a PlayerID column
    immediately before Player, preserving order.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        return df

    if "Player" not in df.columns:
        return df

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("table a[href^='/players/']")
    id_map: dict[str, str] = {}
    for link in links:
        pid = link.get("href", "").rstrip("/").split("/")[-1]
        name = link.get_text(strip=True)
        if pid and name:
            id_map[name] = pid

    if not id_map:
        return df

    df = df.copy()
    df.insert(df.columns.get_loc("Player"), "PlayerID", df["Player"].map(id_map))
    return df


def _extract_roster_table_from_html(html: str) -> Optional[pd.DataFrame]:
    """
    Extract roster info (Name, Hometown, High School, etc.) with PlayerID from links.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        return None

    soup = BeautifulSoup(html, "html.parser")
    # Roster table uses specific id rosters_form_players_*; pick the one with tbody rows.
    candidates = soup.find_all("table", id=lambda x: x and x.startswith("rosters_form_players_"))
    table = None
    for t in candidates:
        tbody = t.find("tbody")
        if tbody and tbody.find("tr"):
            table = t
            break
    if table is None:
        table = soup.find("table", id="stat_grid") or soup.find("table")
    if not table:
        return None

    tbody = table.find("tbody") or table
    header_cells = table.find_all("th")
    headers = [th.get_text(strip=True) for th in header_cells] if header_cells else []
    name_idx = headers.index("Name") if "Name" in headers else None

    rows_data = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        row = []
        for idx, td in enumerate(cells):
            text = td.get_text(strip=True)
            if name_idx is not None and idx == name_idx:
                link = td.find("a")
                pid = None
                if link and link.get("href", "").startswith("/players/"):
                    pid = link.get("href", "").rstrip("/").split("/")[-1]
                row.append(pid)
                row.append(text)
            else:
                row.append(text)
        rows_data.append(row)

    if not rows_data:
        return None

    # Build headers from thead if available, otherwise create generic
    if not headers:
        headers = [f"col{i}" for i in range(len(rows_data[0]))]

    col_builder: list[str] = []
    for idx, h in enumerate(headers):
        if name_idx is not None and idx == name_idx:
            col_builder.append("PlayerID")
            col_builder.append("Player")
        else:
            col_builder.append(h)

    df = pd.DataFrame(rows_data, columns=col_builder)

    rename_map = {
        "#": "Number",
        "Name": "Player",
        "Class": "Yr",
        "Position": "Pos",
        "Height": "Ht",
        "Hometown": "Hometown",
        "High School": "High School",
    }
    for col in list(df.columns):
        lc = col.lower()
        if lc == "player":
            rename_map[col] = "Player"
        if lc == "playerid":
            rename_map[col] = "PlayerID"
    df = df.rename(columns=rename_map)

    if "Number" in df.columns:
        df["Number"] = pd.to_numeric(df["Number"], errors="coerce")

    keep_cols = [
        "Number",
        "PlayerID",
        "Player",
        "Yr",
        "Pos",
        "Ht",
        "Hometown",
        "High School",
    ]
    existing = [c for c in keep_cols if c in df.columns]
    return df[existing]


def fetch_team_player_season_stats(
    teams_df: pd.DataFrame,
    team_id: str,
    include_team_totals: bool = False,
    year_for_roster: Optional[int] = None,
    sleep: float = REQUEST_SLEEP,
    debug_dir: Optional[Path] = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch season-to-date player stats for a single team_id from stats.ncaa.org,
    mirroring ncaavolleyballr::player_season_stats() behavior.

    - If include_team_totals=False, rows like 'TEAM', 'Totals', 'Opponent Totals'
      are removed (like setting team_stats = FALSE in R).
    - If year_for_roster >= 2024, tries to join in Hometown / High School from
      the NCAA roster page.

    Returns a DataFrame or None if stats are not available.
    """
    team_id = str(team_id)

    # Look up metadata from teams_df
    team_meta = teams_df[teams_df["team_id"] == team_id]
    if team_meta.empty:
        raise ValueError(f"team_id {team_id} not found in teams.json mapping")

    # In case there are multiple rows for the same team_id (unlikely), pick one
    team_meta = team_meta.iloc[0]
    season_label = f"{team_meta['yr']}-{team_meta['yr'] + 1}"
    team_name = team_meta["team_name"]
    conference = team_meta.get("conference", None)

    # ----- 1) Fetch season-to-date player stats page -----
    stats_url = f"https://stats.ncaa.org/teams/{team_id}/season_to_date_stats"
    try:
        html = _get_html(stats_url)
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{team_id}_stats.html").write_text(html, encoding="utf-8")
    except requests.HTTPError as e:
        print(f"[WARN] Failed to fetch stats for team_id={team_id}: {e}")
        return None

    try:
        table = _extract_player_table_from_html(html)
    except ValueError as e:
        print(f"[WARN] No player stats table found for team_id={team_id}: {e}")
        return None

    # Rename '#' -> 'Number', match R behavior
    if "#" in table.columns:
        table = table.rename(columns={"#": "Number"})

    # Convert Number to numeric
    if "Number" in table.columns:
        table["Number"] = pd.to_numeric(table["Number"], errors="coerce")

    # Optionally drop TEAM/Totals rows (players only)
    if not include_team_totals:
        if "Player" in table.columns:
            drop_labels = {"TEAM", "Totals", "Opponent Totals"}
            table = table[~table["Player"].isin(drop_labels)]

    # Try to coerce stat columns to numeric, leaving text fields alone
    # Assume columns from 'GP' onwards are numeric, as in the R code.
    if "GP" in table.columns:
        numeric_cols = table.columns[table.columns.get_loc("GP") :]
        for col in numeric_cols:
            table[col] = (
                table[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .replace({"": None})
            )
            table[col] = pd.to_numeric(table[col], errors="coerce")

    # ----- 2) Optionally join roster info (Hometown, High School) -----
    # ncaavolleyballr only does this when yr == 2024; we generalize to >=2024.
    if year_for_roster is None:
        year_for_roster = int(team_meta["yr"])

    roster_df = None
    if year_for_roster >= 2024:
        roster_url = f"https://stats.ncaa.org/teams/{team_id}/roster"
        try:
            roster_html = _get_html(roster_url)
            if debug_dir:
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / f"{team_id}_roster.html").write_text(roster_html, encoding="utf-8")
            roster_df = _extract_roster_table_from_html(roster_html)
        except Exception as e:
            print(f"[WARN] Could not fetch/join roster for team_id={team_id}: {e}")
            roster_df = None

    # If we have roster_df, left-join on (Number, Player == Name)
    if roster_df is not None and not roster_df.empty:
        # We keep roster_df columns distinct from stats columns where possible
        table = table.merge(
            roster_df,
            how="left",
            left_on=["Number"],
            right_on=["Number"],
            suffixes=("", "_roster"),
        )

    # ----- 3) Add metadata (Season, TeamID, Team, Conference) -----
    table.insert(0, "Season", season_label)
    table.insert(1, "TeamID", team_id)
    table.insert(2, "Team", team_name)
    if conference is not None:
        table.insert(3, "Conference", conference)

    # be kind to the server
    time.sleep(sleep)

    return table


def fetch_all_d1_teams_for_year(
    year: int,
    teams_df: pd.DataFrame,
    include_team_totals: bool = False,
    div_filter: int = 1,
    sleep: float = REQUEST_SLEEP,
) -> pd.DataFrame:
    """
    Loop over all teams in a given division and year and fetch stats.

    Returns a concatenated DataFrame with all player rows for that season.
    """
    mask = (teams_df["yr"] == year) & (teams_df["div"] == div_filter)
    subset = teams_df[mask].copy()

    print(
        f"Fetching stats for {len(subset)} teams "
        f"(division {div_filter}, year={year})"
    )

    all_frames: List[pd.DataFrame] = []

    missing: list[dict] = []

    for i, row in subset.iterrows():
        team_id = str(row["team_id"])
        team_name = row["team_name"]
        print(f"[{len(all_frames)+1}/{len(subset)}] {team_name} (team_id={team_id})")

        try:
            df_team = fetch_team_player_season_stats(
                teams_df=teams_df,
                team_id=team_id,
                include_team_totals=include_team_totals,
                year_for_roster=year,
                sleep=sleep,
            )
        except Exception as e:
            print(f"  [ERROR] Skipping {team_name} ({team_id}): {e}")
            missing.append({"team_id": team_id, "team_name": team_name, "error": str(e)})
            continue

        if df_team is not None and not df_team.empty:
            all_frames.append(df_team)

    if not all_frames:
        raise RuntimeError("No team stats could be fetched.")

    return pd.concat(all_frames, ignore_index=True), missing


def fetch_team_roster(
    teams_df: pd.DataFrame,
    team_id: str,
    year: int,
    debug_dir: Optional[Path] = None,
) -> Optional[pd.DataFrame]:
    """Fetch roster for a single team (>=2024) and return normalized DataFrame."""
    team_meta = teams_df[teams_df["team_id"] == str(team_id)]
    if team_meta.empty:
        return None
    team_meta = team_meta.iloc[0]
    conference = team_meta.get("conference", None)
    team_name = team_meta["team_name"]
    season_label = f"{team_meta['yr']}-{team_meta['yr'] + 1}"

    roster_url = f"https://stats.ncaa.org/teams/{team_id}/roster"
    try:
        roster_html = _get_html(roster_url)
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{team_id}_roster.html").write_text(roster_html, encoding="utf-8")
        roster_df = _extract_roster_table_from_html(roster_html)
    except Exception as e:
        print(f"[WARN] Could not fetch roster for team_id={team_id}: {e}")
        return None

    if roster_df is None or roster_df.empty:
        return None

    roster_df.insert(0, "Season", season_label)
    roster_df.insert(1, "TeamID", str(team_id))
    roster_df.insert(2, "Team", team_name)
    if conference is not None:
        roster_df.insert(3, "Conference", conference)
    return roster_df


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Fetch NCAA WVB stats (browser-assisted).")
    parser.add_argument("--year", type=int, default=2025, help="Season year (fall year, e.g., 2025).")
    parser.add_argument("--team", action="append", help="Team name (can be provided multiple times).")
    parser.add_argument("--team-id", action="append", help="Team ID (can be provided multiple times).")
    parser.add_argument("--div", type=int, default=1, help="Division filter (default: 1/DI).")
    parser.add_argument("--output", type=Path, help="Output CSV path. Default: ncaa_wvb_player_stats_d1_<year>.csv")
    parser.add_argument("--roster-output", type=Path, help="Roster CSV path. Default: ncaa_wvb_rosters_d1_<year>.csv")
    parser.add_argument("--headed", action="store_true", help="Run Playwright headed for debugging.")
    parser.add_argument("--min-delay", type=float, default=HUMAN_DELAY_RANGE[0], help="Minimum human delay seconds.")
    parser.add_argument("--max-delay", type=float, default=HUMAN_DELAY_RANGE[1], help="Maximum human delay seconds.")
    parser.add_argument("--debug-html", type=Path, help="Directory to dump fetched HTML snapshots for debugging.")
    parser.add_argument("--no-playwright", action="store_true", help="Force plain HTTP requests (no Playwright). Rate limited to 4 req/sec.")
    parser.add_argument("--user-agent", help="Override User-Agent for requests and Playwright.")
    parser.add_argument("--cookie", help="Cookie header value to include on requests.")
    parser.add_argument("--cookie-file", type=Path, help="Path to a cookie file (plain Cookie header value).")
    args = parser.parse_args()

    # Update globals from CLI
    globals()["HEADLESS"] = not args.headed
    globals()["HUMAN_DELAY_RANGE"] = (args.min_delay, args.max_delay)
    if args.no_playwright:
        globals()["USE_PLAYWRIGHT"] = False
    if args.user_agent:
        globals()["REQUEST_USER_AGENT"] = args.user_agent
    if args.cookie:
        globals()["COOKIE_STR"] = args.cookie
    if args.cookie_file:
        globals()["COOKIE_FILE"] = args.cookie_file

    YEAR = args.year
    teams = load_wvb_teams(YEAR)

    # Collect target team_ids if provided
    target_team_ids: list[str] = []
    if args.team_id:
        target_team_ids.extend([str(tid) for tid in args.team_id])
    if args.team:
        for name in args.team:
            tid = find_team_id(teams, name, YEAR)
            target_team_ids.append(tid)

    # Resolve output paths up front
    base_dir = Path(__file__).resolve().parent
    if args.output:
        out_path = Path(args.output).resolve()
    else:
        out_path = base_dir / f"ncaa_wvb_player_stats_d1_{YEAR}.csv"
    if args.roster_output:
        roster_out = Path(args.roster_output).resolve()
    else:
        roster_out = base_dir / f"ncaa_wvb_rosters_d1_{YEAR}.csv"
    # Optional manifest of completed TeamIDs (one per line)
    manifest_path = out_path.with_name(f"ncaa_wvb_completed_{YEAR}.txt")

    # Resume support: load existing stats/rosters to skip already fetched teams
    stats_existing = None
    roster_existing = None
    existing_stats_ids: set[str] = set()
    existing_roster_ids: set[str] = set()
    if manifest_path.exists():
        try:
            existing_stats_ids |= {line.strip() for line in manifest_path.read_text().splitlines() if line.strip()}
            print(f"[resume] Loaded {len(existing_stats_ids)} completed TeamIDs from manifest.")
        except Exception as e:
            print(f"[resume] Could not read manifest {manifest_path}: {e}")
    if out_path.exists():
        try:
            stats_existing = pd.read_csv(out_path, dtype={"TeamID": str})
            existing_stats_ids |= set(stats_existing["TeamID"].astype(str))
            print(f"[resume] Found existing stats for {len(stats_existing['TeamID'].unique())} teams; skipping those.")
        except Exception as e:
            print(f"[resume] Could not read existing stats file {out_path}: {e}")
    if roster_out.exists():
        try:
            roster_existing = pd.read_csv(roster_out, dtype={"TeamID": str})
            existing_roster_ids |= set(roster_existing["TeamID"].astype(str))
            print(f"[resume] Found existing rosters for {len(roster_existing['TeamID'].unique())} teams; skipping those.")
        except Exception as e:
            print(f"[resume] Could not read existing roster file {roster_out}: {e}")

    if target_team_ids:
        print(f"Fetching stats for {len(target_team_ids)} team(s) in {YEAR}")
        frames: list[pd.DataFrame] = []
        roster_frames: list[pd.DataFrame] = []
        missing: list[dict] = []
        if stats_existing is not None:
            frames.append(stats_existing)
        if roster_existing is not None:
            roster_frames.append(roster_existing)

        to_fetch_stats = [tid for tid in target_team_ids if tid not in existing_stats_ids]
        to_fetch_rosters = [tid for tid in target_team_ids if tid not in existing_roster_ids]
        if existing_stats_ids:
            skipped = [tid for tid in target_team_ids if tid in existing_stats_ids]
            if skipped:
                print(f"[resume] Skipping {len(skipped)} team(s) already present in stats output.")
        if existing_roster_ids:
            skipped_r = [tid for tid in target_team_ids if tid in existing_roster_ids]
            if skipped_r:
                print(f"[resume] Skipping {len(skipped_r)} team(s) already present in roster output.")

        for idx, tid in enumerate(to_fetch_stats, 1):
            print(f"[{idx}/{len(to_fetch_stats)}] team_id={tid}")
            df_team = fetch_team_player_season_stats(
                teams_df=teams,
                team_id=tid,
                include_team_totals=False,
                year_for_roster=YEAR,
                sleep=REQUEST_SLEEP,
                debug_dir=args.debug_html,
            )
            if df_team is not None and not df_team.empty:
                frames.append(df_team)
            else:
                missing.append({"team_id": tid, "team_name": "", "error": "No stats"})
        for tid in to_fetch_rosters:
            roster_df = fetch_team_roster(
                teams_df=teams,
                team_id=tid,
                year=YEAR,
                debug_dir=args.debug_html,
            )
            if roster_df is not None and not roster_df.empty:
                roster_frames.append(roster_df)
        if not frames:
            raise SystemExit("No data fetched for provided teams.")
        all_stats = pd.concat(frames, ignore_index=True)
        all_rosters = pd.concat(roster_frames, ignore_index=True) if roster_frames else pd.DataFrame()
        if missing:
            miss_path = out_path.with_name(f"ncaa_wvb_missing_teams_{YEAR}.csv")
            pd.DataFrame(missing).to_csv(miss_path, index=False)
            print(f"Wrote missing teams list to {miss_path}")
    else:
        # Full pull
        frames: list[pd.DataFrame] = []
        roster_frames: list[pd.DataFrame] = []
        if stats_existing is not None:
            frames.append(stats_existing)
        if roster_existing is not None:
            roster_frames.append(roster_existing)

        fetch_df = teams[(teams["yr"] == YEAR) & (teams["div"] == args.div)]
        fetch_df_stats = fetch_df
        if existing_stats_ids:
            fetch_df_stats = fetch_df_stats[~fetch_df_stats["team_id"].astype(str).isin(existing_stats_ids)]
            print(f"[resume] Skipping {len(existing_stats_ids)} team(s) already present in stats output.")

        if fetch_df_stats.empty:
            all_stats_new = pd.DataFrame()
            missing = []
            print("[resume] No teams left to fetch for stats.")
        else:
            all_stats_new, missing = fetch_all_d1_teams_for_year(
                year=YEAR,
                teams_df=fetch_df_stats,
                include_team_totals=False,  # players only
                div_filter=args.div,
                sleep=REQUEST_SLEEP,
            )
        if frames:
            if not all_stats_new.empty:
                frames.append(all_stats_new)
            all_stats = pd.concat(frames, ignore_index=True)
        else:
            all_stats = all_stats_new
        if missing:
            miss_path = out_path.with_name(f"ncaa_wvb_missing_teams_{YEAR}.csv")
            pd.DataFrame(missing).to_csv(miss_path, index=False)
            print(f"Wrote missing teams list to {miss_path}")
        # Full roster pull
        subset = fetch_df
        if existing_roster_ids:
            subset = subset[~subset["team_id"].astype(str).isin(existing_roster_ids)]
            print(f"[resume] Skipping {len(existing_roster_ids)} team(s) already present in roster output.")
        for idx, row in subset.iterrows():
            tid = str(row["team_id"])
            roster_df = fetch_team_roster(
                teams_df=teams,
                team_id=tid,
                year=YEAR,
                debug_dir=args.debug_html,
            )
            if roster_df is not None and not roster_df.empty:
                roster_frames.append(roster_df)
        all_rosters = pd.concat(roster_frames, ignore_index=True) if roster_frames else pd.DataFrame()

    all_stats.to_csv(out_path, index=False)
    print(f"Wrote {len(all_stats)} stat rows to {out_path}")

    if not all_rosters.empty:
        # Reorder/ensure expected columns
        cols = [
            "Season",
            "TeamID",
            "Team",
            "Conference",
            "Number",
            "PlayerID",
            "Player",
            "Yr",
            "Pos",
            "Ht",
            "Hometown",
            "High School",
        ]
        existing = [c for c in cols if c in all_rosters.columns]
        all_rosters[existing].to_csv(roster_out, index=False)
        print(f"Wrote {len(all_rosters)} roster rows to {roster_out}")
    else:
        print("No rosters captured.")
