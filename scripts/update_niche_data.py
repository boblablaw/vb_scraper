#!/usr/bin/env python3
"""
Update Niche data in settings/teams.json using each team's niche_data_slug.

For every team entry:
  - Fetch https://www.niche.com/colleges/<slug>/
  - Parse overall_grade, academics_grade, value_grade, summary
  - Fetch reviews page and grab first two review bodies as review_pos/review_neg

Writes updated teams.json in place (with pretty indent).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
TEAMS_PATH = ROOT / "settings" / "teams.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vb-scraper-niche/1.0)"
}

# Politics scoring (mirrors existing helper script)
POLITICS_WEIGHTS = {
    "very conservative": -2.0,
    "conservative": -1.0,
    "moderate": 0.0,
    "moderate / independent": 0.0,
    "liberal": 1.0,
    "very liberal": 2.0,
}
POLL_LABELS = [
    "very conservative",
    "conservative",
    "moderate",
    "liberal",
    "very liberal",
]


def fetch_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return None


def extract_grade(text: str, label: str) -> str:
    m = re.search(rf"{label}\s*([A-F][+-]?)", text, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_overall_grade(soup: BeautifulSoup) -> str:
    # Niche shows letter grade prominently; capture first standalone grade token.
    m = re.search(r"\b([A-F][+-]?)\b\s*Overall\s+Grade", soup.get_text(" ", strip=True))
    if m:
        return m.group(1)
    # fallback: first grade badge in page
    badge = soup.find(string=re.compile(r"^[A-F][+-]?$"))
    return badge.strip() if badge else ""


def extract_summary(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    # fallback: first paragraph of main content
    p = soup.find("p")
    return p.get_text(strip=True) if p else ""


def extract_reviews(slug: str) -> tuple[str, str]:
    url = f"https://www.niche.com/colleges/{slug}/reviews/"
    html = fetch_html(url)
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    bodies = []
    # Try structured review bodies
    for tag in soup.find_all(attrs={"itemprop": "reviewBody"}):
        txt = tag.get_text(" ", strip=True)
        if txt:
            bodies.append(txt)
        if len(bodies) >= 2:
            break
    # Fallback to generic paragraphs if nothing found
    if not bodies:
        for p in soup.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if txt:
                bodies.append(txt)
            if len(bodies) >= 2:
                break
    pos = bodies[0] if bodies else ""
    neg = bodies[1] if len(bodies) > 1 else ""
    return pos, neg


def score_to_label(score: float) -> str:
    if score <= -0.8:
        return "very conservative"
    if score <= -0.3:
        return "conservative"
    if score < 0.3:
        return "moderate / independent"
    if score < 0.8:
        return "liberal"
    return "very liberal"


def extract_politics_label(slug: str) -> str:
    """
    Best-effort parse of politics distribution from Niche students page.
    Looks for label + percent pairs, computes weighted score.
    """
    url = f"https://www.niche.com/colleges/{slug}/students/"
    html = fetch_html(url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    matches = re.findall(
        r"(very conservative|conservative|moderate|liberal|very liberal)\\s*(\\d+)%", text
    )
    if not matches:
        return ""

    total = 0
    score = 0.0
    for label, pct_str in matches:
        pct = float(pct_str)
        total += pct
        weight = POLITICS_WEIGHTS.get(label, 0.0)
        score += weight * pct
    if total == 0:
        return ""
    score = score / total
    return score_to_label(score)


def update_team(team: dict) -> bool:
    slug = team.get("niche_data_slug")
    if not slug:
        return False

    url = f"https://www.niche.com/colleges/{slug}/"
    html = fetch_html(url)
    if not html:
        return False

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    niche = team.get("niche", {}) or {}
    before = niche.copy()

    niche["overall_grade"] = extract_overall_grade(soup) or niche.get("overall_grade", "")
    niche["academics_grade"] = extract_grade(text, "Academics") or niche.get("academics_grade", "")
    niche["value_grade"] = extract_grade(text, "Value") or niche.get("value_grade", "")
    niche["summary"] = extract_summary(soup) or niche.get("summary", "")

    pos, neg = extract_reviews(slug)
    if pos:
        niche["review_pos"] = pos
    if neg:
        niche["review_neg"] = neg

    team["niche"] = niche

    # Update politics label (best effort; leave untouched if not found)
    politics_label = extract_politics_label(slug)
    if politics_label:
        team["political_label"] = politics_label

    return (niche != before) or bool(politics_label)


def main():
    parser = argparse.ArgumentParser(description="Update teams.json with Niche data using niche_data_slug.")
    parser.add_argument("--teams-json", type=Path, default=TEAMS_PATH, help="Path to settings/teams.json")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--verbose", action="store_true", help="Print per-team status")
    args = parser.parse_args()

    teams = json.load(open(args.teams_json, "r", encoding="utf-8"))
    updated = 0

    for team in teams:
        name = team.get("team")
        if update_team(team):
            updated += 1
            if args.verbose:
                print(f"[OK] {name}")
        else:
            if args.verbose:
                print(f"[SKIP] {name}")
        time.sleep(args.delay)

    with open(args.teams_json, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2)
        f.write("\n")

    print(f"Updated Niche data for {updated} team(s).")


if __name__ == "__main__":
    main()
