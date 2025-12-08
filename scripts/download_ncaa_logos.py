#!/usr/bin/env python3
"""
Download NCAA logos (light + dark) for every team in settings/teams.json
using henrygd's NCAA API: https://ncaa-api.henrygd.me

- Respects 5 requests/sec limit (we cap at ~4/sec).
- Fuzzy-matches each team to an NCAA `slug` using /schools-index.
- Downloads light and dark SVG logos via /logo/{slug}.svg with ?dark=true.
- Saves them under assets/logos/ncaa/ as:
    assets/logos/ncaa/<Team_Name_Sanitized>_light.svg
    assets/logos/ncaa/<Team_Name_Sanitized>_dark.svg
- Writes back into settings/teams.json:
    "ncaa_slug", "ncaa_logo_light", "ncaa_logo_dark"
- Produces a CSV sanity report at exports/ncaa_logo_mapping.csv
"""

import argparse
import csv
import difflib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ----------- CONFIG -----------

BASE_URL = "https://ncaa-api.henrygd.me"
TEAMS_PATH_DEFAULT = Path("settings/teams.json")
OUTPUT_DIR_DEFAULT = Path("assets/logos/ncaa")
REQUEST_DELAY_SECONDS = 0.25  # 0.25s => max 4 requests/sec (< 5 rps limit)
MAPPING_CSV_DEFAULT = Path("exports/ncaa_logo_mapping.csv")

LOG = logging.getLogger(__name__)


# ----------- HELPERS -----------


def load_teams(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_teams(path: Path, teams: List[Dict[str, Any]]) -> None:
    path.write_text(json.dumps(teams, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_name_from_team(team_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", team_name).strip("_")


def save_logo(content: bytes, team_name: str, variant: str, output_dir: Path) -> Path:
    """
    variant: "light" or "dark"
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_name_from_team(team_name)
    filename = f"{safe_name}_{variant}.svg"
    out_path = output_dir / filename
    out_path.write_bytes(content)
    return out_path


def normalize_name(name: str) -> str:
    """
    Normalize school names for fuzzy matching.
    - Lowercase
    - Remove 'university', 'the', 'at', 'of', 'state', 'college'
    - Remove punctuation
    """
    s = name.lower()
    for token in ["university", "the", "college", "at", "of", "state", "campus"]:
        s = re.sub(rf"\b{token}\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fetch_schools_index() -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/schools-index"
    LOG.info("Fetching schools index from %s", url)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError(f"/schools-index returned unexpected payload: {type(data)}")
    return data


def build_school_lookup(
    schools: List[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    Returns:
      - list of normalized names
      - mapping from normalized name to school dict including 'slug' and 'display_name'
    """
    norm_names: List[str] = []
    by_norm: Dict[str, Dict[str, Any]] = {}

    for s in schools:
        slug = s.get("slug") or s.get("seo") or s.get("team_seo")
        if not slug:
            continue

        name_candidates = [
            s.get("name"),
            s.get("long_name"),
            s.get("longName"),
            s.get("full"),
        ]
        base_name = next(
            (n for n in name_candidates if isinstance(n, str) and n.strip()), slug
        )
        norm = normalize_name(base_name)
        if not norm:
            continue

        if norm in by_norm:
            LOG.debug(
                "Name collision for normalized '%s' (%s vs %s)",
                norm,
                by_norm[norm].get("slug"),
                slug,
            )
            continue

        by_norm[norm] = {
            **s,
            "slug": slug,
            "display_name": base_name,
        }
        norm_names.append(norm)

    return norm_names, by_norm


def match_team_to_slug(
    team: Dict[str, Any],
    norm_names: List[str],
    by_norm: Dict[str, Dict[str, Any]],
    threshold: float = 0.78,
) -> Tuple[Optional[Dict[str, Any]], str, float]:
    """
    Given a team dict from teams.json, return:
      - matched school dict from NCAA index OR None
      - match_type: "exact", "fuzzy", or "none"
      - match_score: 0.0..1.0 (0 if none)
    """
    aliases: List[str] = []

    # 1) exact team name
    if team.get("team"):
        aliases.append(team["team"])

    # 2) short_name
    if team.get("short_name") and team["short_name"] not in aliases:
        aliases.append(team["short_name"])

    # 3) explicit aliases list
    for a in team.get("team_name_aliases", []):
        if isinstance(a, str) and a not in aliases:
            aliases.append(a)

    best_choice: Optional[Dict[str, Any]] = None
    best_score = 0.0
    best_type = "none"

    for alias in aliases:
        norm_alias = normalize_name(alias)
        if not norm_alias:
            continue

        # Exact normalized match
        if norm_alias in by_norm:
            school = by_norm[norm_alias]
            LOG.info(
                "Exact match: '%s' -> '%s' (slug=%s)",
                alias,
                school["display_name"],
                school["slug"],
            )
            return school, "exact", 1.0

        # Fuzzy match
        match = difflib.get_close_matches(norm_alias, norm_names, n=1, cutoff=threshold)
        if match:
            candidate_norm = match[0]
            score = difflib.SequenceMatcher(None, norm_alias, candidate_norm).ratio()
            if score > best_score:
                best_score = score
                best_choice = by_norm[candidate_norm]
                best_type = "fuzzy"

    if best_choice:
        LOG.warning(
            "Fuzzy match (score=%.3f): '%s' -> '%s' (slug=%s)",
            best_score,
            team.get("team"),
            best_choice["display_name"],
            best_choice["slug"],
        )
        return best_choice, best_type, best_score

    LOG.error(
        "No suitable NCAA slug found for team '%s' (aliases=%s)",
        team.get("team"),
        aliases,
    )
    return None, "none", 0.0


def download_logo(slug: str, variant: str) -> Optional[bytes]:
    """
    variant: "light" or "dark"
    """
    params = {}
    if variant == "dark":
        params["dark"] = "true"

    url = f"{BASE_URL}/logo/{slug}.svg"
    try:
        resp = requests.get(url, params=params, timeout=15)
    except Exception as e:
        LOG.error("Error fetching %s logo for slug '%s': %s", variant, slug, e)
        return None

    if resp.status_code != 200:
        LOG.error(
            "Failed to fetch %s logo for slug '%s': HTTP %s",
            variant,
            slug,
            resp.status_code,
        )
        return None

    return resp.content


def main():
    parser = argparse.ArgumentParser(
        description="Download NCAA logos (light/dark) for teams in settings/teams.json"
    )
    parser.add_argument(
        "--teams-path",
        type=Path,
        default=TEAMS_PATH_DEFAULT,
        help="Path to teams.json (default: settings/teams.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR_DEFAULT,
        help="Directory to save logos (default: assets/logos/ncaa)",
    )
    parser.add_argument(
        "--mapping-csv",
        type=Path,
        default=MAPPING_CSV_DEFAULT,
        help="Path for CSV mapping report (default: exports/ncaa_logo_mapping.csv)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip download if both light and dark logo files already exist",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    teams_path: Path = args.teams_path
    output_dir: Path = args.output_dir
    mapping_csv_path: Path = args.mapping_csv

    LOG.info("Loading teams from %s", teams_path)
    teams = load_teams(teams_path)
    LOG.info("Loaded %d teams", len(teams))

    schools = fetch_schools_index()
    norm_names, by_norm = build_school_lookup(schools)
    LOG.info("Loaded %d schools from NCAA index", len(by_norm))

    # Prepare CSV
    mapping_csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_rows: List[Dict[str, Any]] = []

    failures: List[str] = []

    for team in teams:
        team_name = team.get("team") or team.get("short_name") or "UNKNOWN"
        LOG.info("Processing team: %s", team_name)

        school, match_type, match_score = match_team_to_slug(
            team, norm_names, by_norm
        )

        if not school:
            failures.append(team_name)
            csv_rows.append(
                {
                    "team": team_name,
                    "ncaa_display_name": "",
                    "ncaa_slug": "",
                    "match_type": match_type,
                    "match_score": f"{match_score:.3f}",
                    "logo_light": "",
                    "logo_dark": "",
                    "status": "no_match",
                }
            )
            continue

        slug = school["slug"]
        display_name = school.get("display_name", slug)
        LOG.debug("Using slug '%s' for team '%s'", slug, team_name)

        safe_name = safe_name_from_team(team_name)
        light_path = output_dir / f"{safe_name}_light.svg"
        dark_path = output_dir / f"{safe_name}_dark.svg"

        light_rel = str(light_path)
        dark_rel = str(dark_path)

        # Skip if requested and both exist
        if args.skip_existing and light_path.exists() and dark_path.exists():
            LOG.info("Skipping %s (logos already exist)", team_name)
            status = "skipped_existing"
        else:
            # Download light
            content = download_logo(slug, "light")
            time.sleep(REQUEST_DELAY_SECONDS)
            if content:
                out_light = save_logo(content, team_name, "light", output_dir)
                LOG.info("Saved light logo -> %s", out_light)
            else:
                failures.append(f"{team_name} (light)")
                csv_rows.append(
                    {
                        "team": team_name,
                        "ncaa_display_name": display_name,
                        "ncaa_slug": slug,
                        "match_type": match_type,
                        "match_score": f"{match_score:.3f}",
                        "logo_light": "",
                        "logo_dark": "",
                        "status": "light_failed",
                    }
                )
                continue

            # Download dark
            content = download_logo(slug, "dark")
            time.sleep(REQUEST_DELAY_SECONDS)
            if content:
                out_dark = save_logo(content, team_name, "dark", output_dir)
                LOG.info("Saved dark logo -> %s", out_dark)
                status = "ok"
            else:
                failures.append(f"{team_name} (dark)")
                csv_rows.append(
                    {
                        "team": team_name,
                        "ncaa_display_name": display_name,
                        "ncaa_slug": slug,
                        "match_type": match_type,
                        "match_score": f"{match_score:.3f}",
                        "logo_light": light_rel,
                        "logo_dark": "",
                        "status": "dark_failed",
                    }
                )
                continue

        # Update team dict with slug + logo paths
        team["ncaa_slug"] = slug
        team["ncaa_logo_light"] = light_rel
        team["ncaa_logo_dark"] = dark_rel

        csv_rows.append(
            {
                "team": team_name,
                "ncaa_display_name": display_name,
                "ncaa_slug": slug,
                "match_type": match_type,
                "match_score": f"{match_score:.3f}",
                "logo_light": light_rel,
                "logo_dark": dark_rel,
                "status": status,
            }
        )

    # Write updated teams.json
    LOG.info("Writing updated teams to %s", teams_path)
    save_teams(teams_path, teams)

    # Write CSV mapping
    LOG.info("Writing mapping CSV to %s", mapping_csv_path)
    with mapping_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "team",
                "ncaa_display_name",
                "ncaa_slug",
                "match_type",
                "match_score",
                "logo_light",
                "logo_dark",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    LOG.info("Done.")
    if failures:
        LOG.warning("Some teams/logos failed to download:")
        for f in failures:
            LOG.warning("  - %s", f)


if __name__ == "__main__":
    main()
