"""
Auto-populate `logo_map_name` in settings/teams.json based on files in report_builder/logos.

Usage (from repo root):
  python scripts/auto_populate_logos.py
  python scripts/auto_populate_logos.py --teams settings/teams.json --logos report_builder/logos

The script:
  - Loads the teams JSON.
  - Scans the logos directory for image files.
  - Normalizes names and tries:
      1) Exact normalized match on team / short_name / aliases.
      2) Fuzzy match (difflib) with a high similarity cutoff.
  - Writes updated teams JSON in-place (with a simple backup file alongside it).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def normalize_name(value: str) -> str:
    """
    Normalize school / logo names for matching.

    - Lowercase
    - Replace '&' with 'and'
    - Remove non-alphanumeric characters
    """
    value = value.strip().lower()
    value = value.replace("&", "and")
    # collapse common words like 'the' only when standalone, but keep it simple for now
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def logo_penalty(basename: str) -> int:
    """
    Small heuristic to prefer 'clean' primary logos over variants like *_NEW, *_ALT.
    Lower score is better.
    """
    name = basename.lower()
    penalty = 0
    for token in ("new", "alt", "alternate", "wordmark", "secondary"):
        if token in name:
            penalty += 1
    return penalty


@dataclass
class LogoMatchResult:
    filename: str
    method: str  # "exact" or "fuzzy"
    score: float


def build_logo_index(logos_dir: Path) -> Tuple[Dict[str, List[str]], List[str], Dict[str, str]]:
    """
    Build an index of logo files:
      - norm_key -> [filenames]
      - all_norm_keys: list of normalized keys
      - norm_key_to_best_file: a single 'best' filename per normalized key
    """
    if not logos_dir.exists():
        raise FileNotFoundError(f"Logos directory not found: {logos_dir}")

    norm_to_files: Dict[str, List[str]] = {}
    for path in logos_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
            continue
        basename = path.stem  # without extension
        norm = normalize_name(basename)
        if not norm:
            continue
        norm_to_files.setdefault(norm, []).append(path.name)

    norm_key_to_best_file: Dict[str, str] = {}
    for norm_key, files in norm_to_files.items():
        if len(files) == 1:
            norm_key_to_best_file[norm_key] = files[0]
        else:
            # Choose lowest-penalty file if multiple share same normalized key
            best = min(files, key=lambda f: logo_penalty(Path(f).stem))
            norm_key_to_best_file[norm_key] = best

    all_norm_keys = list(norm_key_to_best_file.keys())
    return norm_to_files, all_norm_keys, norm_key_to_best_file


def choose_best_logo(
    candidates: Iterable[str],
    norm_to_files: Dict[str, List[str]],
    all_norm_keys: List[str],
    norm_key_to_best_file: Dict[str, str],
    fuzzy_cutoff: float = 0.88,
) -> Optional[LogoMatchResult]:
    """
    Given candidate team names / aliases, return the best matching logo file.

    Strategy:
      1. Try exact normalized key matches.
      2. If none found, use difflib on normalized strings with a relatively
         high cutoff to avoid obviously wrong matches.
    """
    # 1) Exact normalized match
    for candidate in candidates:
        if not candidate:
            continue
        norm = normalize_name(candidate)
        if not norm:
            continue
        if norm in norm_key_to_best_file:
            filename = norm_key_to_best_file[norm]
            return LogoMatchResult(filename=filename, method="exact", score=1.0)

    # 2) Fuzzy match across all normalized keys
    best: Optional[LogoMatchResult] = None
    for candidate in candidates:
        if not candidate:
            continue
        norm = normalize_name(candidate)
        if not norm:
            continue
        # use get_close_matches to narrow candidates
        close = get_close_matches(norm, all_norm_keys, n=3, cutoff=fuzzy_cutoff)
        for match_norm in close:
            filename = norm_key_to_best_file[match_norm]
            score = SequenceMatcher(None, norm, match_norm).ratio()
            if score < fuzzy_cutoff:
                continue
            if best is None or score > best.score:
                best = LogoMatchResult(filename=filename, method="fuzzy", score=score)

    return best


def update_teams_with_logos(teams_path: Path, logos_dir: Path, dry_run: bool = False) -> None:
    teams_data = json.loads(teams_path.read_text())
    if not isinstance(teams_data, list):
        raise ValueError(f"Expected list in {teams_path}, got {type(teams_data)}")

    norm_to_files, all_norm_keys, norm_key_to_best_file = build_logo_index(logos_dir)

    # Quick index of existing filenames to validate already-set logo_map_name fields.
    existing_filenames = {fn for files in norm_to_files.values() for fn in files}

    unchanged = 0
    exact_matches = 0
    fuzzy_matches = 0
    missing: List[Tuple[str, str]] = []  # (team name, short_name)

    for team in teams_data:
        team_name = team.get("team") or ""
        short_name = team.get("short_name") or ""
        current = (team.get("logo_map_name") or "").strip()

        # If already set and file exists, keep it.
        if current and current in existing_filenames:
            unchanged += 1
            continue

        candidates: List[str] = [team_name, short_name]
        aliases = team.get("team_name_aliases") or []
        if isinstance(aliases, list):
            candidates.extend(str(a) for a in aliases if a)

        match = choose_best_logo(
            candidates=candidates,
            norm_to_files=norm_to_files,
            all_norm_keys=all_norm_keys,
            norm_key_to_best_file=norm_key_to_best_file,
        )

        if match is None:
            missing.append((team_name, short_name))
            continue

        if not dry_run:
            team["logo_map_name"] = match.filename

        if match.method == "exact":
            exact_matches += 1
        else:
            fuzzy_matches += 1

    if not dry_run:
        backup_path = teams_path.with_suffix(teams_path.suffix + ".bak")
        if not backup_path.exists():
            backup_path.write_text(teams_path.read_text())
        teams_path.write_text(json.dumps(teams_data, indent=2, ensure_ascii=False))

    print(f"Teams processed: {len(teams_data)}")
    print(f"  Unchanged (valid existing logo_map_name): {unchanged}")
    print(f"  Exact matches assigned: {exact_matches}")
    print(f"  Fuzzy matches assigned: {fuzzy_matches}")
    print(f"  No match found: {len(missing)}")
    if missing:
        print("\nExamples with no logo match (up to 20):")
        for team_name, short_name in missing[:20]:
            print(f"  - {team_name} ({short_name})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-populate logo_map_name in teams.json using logos folder.")
    parser.add_argument(
        "--teams",
        type=Path,
        default=Path("settings/teams.json"),
        help="Path to teams JSON file (default: settings/teams.json)",
    )
    parser.add_argument(
        "--logos",
        type=Path,
        default=Path("report_builder/logos"),
        help="Path to logos directory (default: report_builder/logos)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write changes, just print summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_teams_with_logos(args.teams, args.logos, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

