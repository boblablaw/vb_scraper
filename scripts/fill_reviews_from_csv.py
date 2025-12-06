from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[1]
TEAMS_JSON = ROOT / "settings" / "teams.json"
REVIEWS_CSV = ROOT / "settings" / "school_reviews.csv"


def load_reviews() -> Dict[str, Dict[str, str]]:
    reviews: Dict[str, Dict[str, str]] = {}
    with REVIEWS_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = (row.get("team") or "").strip()
            if not team:
                continue
            reviews[team] = {
                "summary": (row.get("summary") or "").strip(),
                "review_pos": (row.get("review_pos") or "").strip(),
                "review_neg": (row.get("review_neg") or "").strip(),
            }
    print(f"Loaded {len(reviews)} review rows from {REVIEWS_CSV.name}")
    return reviews


def main() -> None:
    with TEAMS_JSON.open(encoding="utf-8") as f:
        teams = json.load(f)

    review_map = load_reviews()
    updated = 0
    missing = []

    # Build a quick index by team name and short_name for flexibility
    index: Dict[str, Dict[str, Any]] = {}
    for s in teams:
        team_name = (s.get("team") or "").strip()
        short_name = (s.get("short_name") or "").strip()
        if team_name:
            index[team_name] = s
        if short_name and short_name != team_name:
            index.setdefault(short_name, s)

    for key, r in review_map.items():
        s = index.get(key)
        if not s:
            missing.append(key)
            continue

        niche = s.setdefault("niche", {})

        if r["summary"]:
            niche["summary"] = r["summary"]
        if r["review_pos"]:
            niche["review_pos"] = f"\"{r['review_pos']}\""
        if r["review_neg"]:
            niche["review_neg"] = f"\"{r['review_neg']}\""

        updated += 1

    with TEAMS_JSON.open("w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Updated reviews for {updated} schools.")
    if missing:
        print("Reviews CSV schools not found in teams.json:")
        for name in missing:
            print("  -", name)


if __name__ == "__main__":
    main()