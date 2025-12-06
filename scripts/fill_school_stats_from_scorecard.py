from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
TEAMS_JSON = ROOT / "settings" / "teams.json"
SCORECARD_CSV = ROOT / "external_data" / "college_scorecard_most_recent.csv"


# ------------------------- Basic helpers -------------------------


def normalize_name(s: str) -> str:
    """
    Crude normalization for school name matching:
    - lowercases
    - removes punctuation and common words
    - turns '&' into 'and'
    """
    if not s:
        return ""

    s = s.lower()
    rep_map = {
        "&": " and ",
        ",": " ",
        ".": " ",
        "-": " ",
        "’": "",
        "'": "",
    }
    for k, v in rep_map.items():
        s = s.replace(k, v)

    drop_words = {
        "the",
        "university",
        "college",
        "state",
        "of",
        "at",
        "campus",
        "city",
        "institution",
    }
    parts = [p for p in s.split() if p not in drop_words]
    return " ".join(parts).strip()


def safe_float(row: Dict[str, str], key: str) -> Optional[float]:
    v = row.get(key)
    if v is None or v == "" or v in ("NULL", "PrivacySuppressed"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def safe_int(row: Dict[str, str], key: str) -> Optional[int]:
    v = row.get(key)
    if v is None or v == "" or v in ("NULL", "PrivacySuppressed"):
        return None
    try:
        return int(round(float(v)))
    except ValueError:
        return None


def first_nonempty(row: Dict[str, str], *keys: str) -> str:
    """
    Return the first non-empty, non-NULL, non-PrivacySuppressed value
    for the given keys, or "" if none found.
    """
    for key in keys:
        if key not in row:
            continue
        v = (row.get(key) or "").strip()
        if v and v not in ("NULL", "PrivacySuppressed"):
            return v
    return ""


# -------------------- Scorecard loading/index --------------------


def load_scorecard_index() -> tuple[
    Dict[str, Dict[str, str]],
    Dict[str, Dict[str, str]],
    List[Tuple[str, Dict[str, str]]],
]:
    """
    Load the College Scorecard CSV and build:
      - index_by_name: dict[normalized_name] -> row
      - index_by_unitid: dict[UNITID] -> row
      - all_rows: list of (normalized_name, row) for fuzzy matching
    """
    index_by_name: Dict[str, Dict[str, str]] = {}
    index_by_unitid: Dict[str, Dict[str, str]] = {}
    all_rows: List[Tuple[str, Dict[str, str]]] = []

    with SCORECARD_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inst_name = (row.get("INSTNM") or "").strip()
            if not inst_name:
                continue

            norm = normalize_name(inst_name)
            if not norm:
                continue

            all_rows.append((norm, row))

            if norm not in index_by_name:
                index_by_name[norm] = row

            unitid = (row.get("UNITID") or "").strip()
            if unitid and unitid not in index_by_unitid:
                index_by_unitid[unitid] = row

    print(f"Loaded {len(all_rows)} institutions from Scorecard.")
    return index_by_name, index_by_unitid, all_rows


# ------------------- Matching / similarity -------------------


def name_similarity(a: str, b: str) -> float:
    """
    Simple similarity between two normalized names using token Jaccard overlap.
    Returns a value between 0 and 1.
    """
    if not a or not b:
        return 0.0
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union


def find_best_match(
    name_candidates: List[str],
    index_by_name: Dict[str, Dict[str, str]],
    all_rows: List[Tuple[str, Dict[str, str]]],
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """
    Given a list of candidate names for a team (team, short_name, aliases),
    try to find the best Scorecard row.

    Returns (row, confidence) where confidence is one of:
      - "high"   -> exact normalized name match
      - "medium" -> good fuzzy match (similarity >= 0.80)
      - "low"    -> weaker fuzzy match but still above threshold
      - (None, None) if no usable match
    """
    tried_norms: List[str] = []
    for cand in name_candidates:
        norm = normalize_name(cand)
        if not norm:
            continue
        if norm not in tried_norms:
            tried_norms.append(norm)

        row = index_by_name.get(norm)
        if row:
            return row, "high"

    if not tried_norms:
        return None, None

    best_row: Optional[Dict[str, str]] = None
    best_score = 0.0

    # Fuzzy over all institutions
    for norm_row, row in all_rows:
        if not norm_row:
            continue
        for norm in tried_norms:
            sim = name_similarity(norm, norm_row)
            if sim > best_score:
                best_score = sim
                best_row = row

    if best_row is None:
        return None, None

    if best_score < 0.60:
        return None, None
    if best_score >= 0.80:
        return best_row, "medium"
    return best_row, "low"


# ------------------- Scoring / grading -------------------


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def scale_salary_to_score(salary: Optional[float]) -> Optional[float]:
    """
    Map salary (e.g. 30k–80k) -> 0–100.
    """
    if salary is None:
        return None
    lo, hi = 30000.0, 80000.0
    t = (salary - lo) / (hi - lo)
    return clamp01(t) * 100.0


def scale_cost_to_score(cost: Optional[float]) -> Optional[float]:
    """
    Lower net cost is better. Roughly map 10k–70k -> 100–0.
    """
    if cost is None:
        return None
    lo, hi = 10000.0, 70000.0
    t = (hi - cost) / (hi - lo)
    return clamp01(t) * 100.0


def grade_from_score(score: float) -> str:
    """
    Convert 0–100 numeric score into a letter grade similar to a Niche-like scale.
    """
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 60:
        return "D"
    return "D-"


def weighted_score(
    components: List[Tuple[Optional[float], float]]
) -> Optional[float]:
    """
    components: list of (value, weight), where value may be None.
    Returns a weighted average over non-None components, or None if all are None.
    """
    total_w = 0.0
    total = 0.0
    for value, w in components:
        if value is None:
            continue
        total_w += w
        total += value * w
    if total_w == 0.0:
        return None
    return total / total_w


def compute_scores_from_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Given a Scorecard row, compute:
      - undergrad_enrollment
      - total_enrollment (approx)
      - acceptance_rate (%)
      - graduation_rate (%)
      - median_starting_salary
      - avg_cost_after_aid
      - retention_rate
      - overall_score, academic_score, value_score (0–100)
      - overall_grade, academic_grade, value_grade
    """
    undergrad_enrollment = safe_int(row, "UGDS")
    total_enrollment = undergrad_enrollment

    acceptance_rate = safe_float(row, "ADM_RATE")
    if acceptance_rate is not None:
        acceptance_rate *= 100.0

    graduation_rate = safe_float(row, "C150_4")
    if graduation_rate is not None:
        graduation_rate *= 100.0

    median_starting_salary = safe_float(row, "MD_EARN_WNE_P10")
    avg_cost_after_aid = safe_float(row, "AVG_COST")

    retention_rate = safe_float(row, "RET_FT4")
    if retention_rate is not None:
        retention_rate *= 100.0

    grad_score = graduation_rate if graduation_rate is not None else None
    salary_score = scale_salary_to_score(median_starting_salary)
    cost_score = scale_cost_to_score(avg_cost_after_aid)
    retention_score = retention_rate if retention_rate is not None else None

    academic_score = weighted_score(
        [
            (grad_score, 0.4),
            (retention_score, 0.3),
            (salary_score, 0.3),
        ]
    )

    value_score = weighted_score(
        [
            (salary_score, 0.6),
            (cost_score, 0.4),
        ]
    )

    overall_score = weighted_score(
        [
            (academic_score, 0.5),
            (value_score, 0.4),
            (grad_score, 0.1),
        ]
    )

    result: Dict[str, Any] = {
        "undergrad_enrollment": undergrad_enrollment,
        "total_enrollment": total_enrollment,
        "acceptance_rate": acceptance_rate,
        "graduation_rate": graduation_rate,
        "median_starting_salary": median_starting_salary,
        "avg_cost_after_aid": avg_cost_after_aid,
        "retention_rate": retention_rate,
        "academic_score": academic_score,
        "value_score": value_score,
        "overall_score": overall_score,
    }

    if academic_score is not None:
        result["academic_grade"] = grade_from_score(academic_score)
    if value_score is not None:
        result["value_grade"] = grade_from_score(value_score)
    if overall_score is not None:
        result["overall_grade"] = grade_from_score(overall_score)

    return result


# ------------------- Score explanation helpers -------------------


def letter_to_rank(letter: str) -> int:
    """
    Map a letter grade to an ordinal rank so we can talk about
    how far apart Niche vs Scorecard grades are.
    Lower index = stronger grade.
    """
    scale = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"]
    if not letter:
        return len(scale) // 2
    up = letter.strip().upper()
    if up not in scale:
        return len(scale) // 2
    return scale.index(up)


def build_score_explanation(scores: Dict[str, Any], niche: Dict[str, Any]) -> str:
    """
    Build a human-readable explanation of why the scorecard grades
    look the way they do, and how they relate to Niche's grades
    if those are present.
    """
    overall_grade = scores.get("overall_grade")
    academic_grade = scores.get("academic_grade")
    value_grade = scores.get("value_grade")

    grad = scores.get("graduation_rate")
    retention = scores.get("retention_rate")
    salary = scores.get("median_starting_salary")
    cost = scores.get("avg_cost_after_aid")
    acceptance = scores.get("acceptance_rate")

    niche_overall = (niche.get("overall_grade") or "").strip()

    pieces: List[str] = []

    # High-level summary
    if overall_grade:
        pieces.append(
            f"Our Scorecard-based model rates this school around a {overall_grade} overall."
        )

    if academic_grade or value_grade:
        sub_bits: List[str] = []
        if academic_grade:
            sub_bits.append(f"{academic_grade} for academics")
        if value_grade:
            sub_bits.append(f"{value_grade} for value")
        if sub_bits:
            pieces.append("That breaks down to " + " and ".join(sub_bits) + ".")

    # Compare to Niche if we have their overall grade
    if overall_grade and niche_overall:
        our_rank = letter_to_rank(overall_grade)
        niche_rank = letter_to_rank(niche_overall)
        diff = our_rank - niche_rank  # positive = our model is harsher

        if abs(diff) >= 2:
            if diff > 0:
                pieces.append(
                    f"Niche lists the overall experience closer to a {niche_overall}, "
                    "but federal outcome data (graduation, cost, and earnings) make it look weaker in this model."
                )
            else:
                pieces.append(
                    f"Niche lists the overall experience around a {niche_overall}, "
                    "but based on Scorecard outcomes this model sees somewhat stronger performance."
                )
        else:
            pieces.append(
                f"Niche’s overall grade of {niche_overall} is broadly in line with this Scorecard-based estimate."
            )

    # Metric-driven explanation
    metric_bits: List[str] = []

    if grad is not None:
        if grad >= 75:
            metric_bits.append(f"graduation rate is solid at roughly {grad:.0f}%")
        elif grad >= 60:
            metric_bits.append(f"graduation rate is moderate at about {grad:.0f}%")
        else:
            metric_bits.append(
                f"graduation rate is on the low side at around {grad:.0f}%, which drags down academics"
            )

    if retention is not None:
        if retention >= 85:
            metric_bits.append(
                f"first-year retention is strong at about {retention:.0f}%"
            )
        elif retention < 75:
            metric_bits.append(
                f"first-year retention is somewhat low at about {retention:.0f}%"
            )

    if salary is not None:
        if salary >= 65000:
            metric_bits.append(
                f"alumni earnings are high, with median 10-year salaries around ${salary:,.0f}"
            )
        elif salary >= 50000:
            metric_bits.append(
                f"alumni earnings are decent, with median 10-year salaries around ${salary:,.0f}"
            )
        else:
            metric_bits.append(
                f"median 10-year earnings are relatively modest at about ${salary:,.0f}"
            )

    if cost is not None:
        if cost <= 20000:
            metric_bits.append(
                f"average annual cost after aid is relatively low at roughly ${cost:,.0f}, helping the value score"
            )
        elif cost <= 35000:
            metric_bits.append(
                f"average annual cost after aid is mid-range at about ${cost:,.0f}"
            )
        else:
            metric_bits.append(
                f"average annual cost after aid is on the higher side at roughly ${cost:,.0f}, which hurts value"
            )

    if acceptance is not None:
        if acceptance <= 30:
            metric_bits.append(
                f"admission is fairly selective with an acceptance rate near {acceptance:.0f}%"
            )
        elif acceptance >= 75:
            metric_bits.append(
                f"admission is relatively open with an acceptance rate around {acceptance:.0f}%"
            )

    if metric_bits:
        if len(metric_bits) > 3:
            metric_bits = metric_bits[:3]
        pieces.append(
            "Key drivers behind these grades: " + "; ".join(metric_bits) + "."
        )

    return " ".join(pieces).strip()


# --------------------------- Main ---------------------------


def main() -> None:
    with TEAMS_JSON.open(encoding="utf-8") as f:
        teams = json.load(f)

    index_by_name, index_by_unitid, all_rows = load_scorecard_index()

    matched = 0
    unmatched: List[str] = []

    for s in teams:
        team_name = s.get("team") or ""
        short_name = s.get("short_name") or ""

        # 1) Prefer an explicit unitid in the team record; if present, treat it as authoritative.
        unitid_field = (s.get("unitid") or "").strip()
        override_unitid = (s.get("scorecard_unitid") or "").strip()
        scorecard_row: Optional[Dict[str, str]] = None
        confidence: Optional[str] = None

        if unitid_field:
            override_unitid = unitid_field
            s["scorecard_unitid"] = unitid_field

        if override_unitid:
            scorecard_row = index_by_unitid.get(override_unitid)
            if scorecard_row:
                confidence = "override"
            else:
                # fall back to name-based matching, but keep this visible for debugging
                print(
                    f"Warning: scorecard_unitid={override_unitid} "
                    f"for '{team_name or short_name}' not found in Scorecard index; "
                    "falling back to name matching."
                )

        # 2) If no valid override, fall back to name/alias-based matching
        if scorecard_row is None:
            name_candidates: List[str] = []
            if team_name:
                name_candidates.append(team_name)
            if short_name and short_name != team_name:
                name_candidates.append(short_name)
            for alias in s.get("team_name_aliases", []):
                if alias not in name_candidates:
                    name_candidates.append(alias)

            scorecard_row, confidence = find_best_match(
                name_candidates, index_by_name, all_rows
            )

            # If this is our first time matching AND the match is high confidence,
            # automatically store the unitid in teams.json so future runs use it.
            if scorecard_row is not None and confidence == "high":
                unitid = (scorecard_row.get("UNITID") or "").strip()
                if unitid:
                    s["scorecard_unitid"] = unitid

        if not scorecard_row:
            s["scorecard_confidence"] = "unmatched"
            unmatched.append(team_name or short_name)
            continue

        scores = compute_scores_from_row(scorecard_row)
        matched += 1

        s["scorecard_confidence"] = confidence or "unknown"
        s["scorecard_match_name"] = scorecard_row.get("INSTNM")

        # Promote key numeric fields to top-level for your School Snapshot block.
        for key in (
            "undergrad_enrollment",
            "total_enrollment",
            "acceptance_rate",
            "graduation_rate",
            "median_starting_salary",
            "avg_cost_after_aid",
        ):
            if scores.get(key) is not None:
                s[key] = scores[key]

        # Fill niche-style grades only if missing (so you don't overwrite manual tweaks).
        niche = s.setdefault("niche", {})
        if scores.get("overall_grade") and not niche.get("overall_grade"):
            niche["overall_grade"] = scores["overall_grade"]
        if scores.get("academic_grade") and not niche.get("academics_grade"):
            niche["academics_grade"] = scores["academic_grade"]
        if scores.get("value_grade") and not niche.get("value_grade"):
            niche["value_grade"] = scores["value_grade"]

        # Build a human-readable explanation of why the grades look the way they do
        explanation = build_score_explanation(scores, niche)
        if explanation:
            s["score_explanation"] = explanation

        # Attach a compact "scorecard" block so you can inspect/debug later.
        s["scorecard"] = {
            "unitid": scorecard_row.get("UNITID"),
            "instnm": scorecard_row.get("INSTNM"),
            "confidence": confidence or "unknown",
            "score_explanation": explanation,
            **{k: v for k, v in scores.items()},
        }

        # -------- Geo fields from Scorecard (override only if Scorecard has data) --------
        city = first_nonempty(scorecard_row, "CITY")
        if city:
            s["city"] = city

        state = first_nonempty(scorecard_row, "STABBR", "STATE")
        if state:
            s["state"] = state

        zip_code = first_nonempty(scorecard_row, "ZIP", "ZIP5")
        if zip_code:
            s["zip_code"] = zip_code

        county = first_nonempty(scorecard_row, "COUNTYNAME", "COUNTYNM", "COUNTY")
        if county:
            s["county"] = county

        # Derive city_state if both available
        if city and state:
            s["city_state"] = f"{city}, {state}"

        lat = safe_float(scorecard_row, "LATITUDE")
        lon = safe_float(scorecard_row, "LONGITUDE")
        if lat is not None:
            s["lat"] = lat
        if lon is not None:
            s["lon"] = lon

    with TEAMS_JSON.open("w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Matched {matched} teams to Scorecard.")
    if unmatched:
        print("Unmatched teams (check naming or handle manually):")
        for name in unmatched:
            print("  -", name)


if __name__ == "__main__":
    main()
