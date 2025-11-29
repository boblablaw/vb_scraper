#!/usr/bin/env python3
"""
Validate export data quality: names, emails, phones, titles, positions, stats.

Usage:
    python scripts/validate_exports.py              # Basic validation
    python scripts/validate_exports.py --full       # Full validation with detailed report
"""

import argparse
import glob
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

# Append parent to sys.path to import project modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import excel_unprotect, normalize_player_name, extract_position_codes

EXPORTS_DIR = "exports"

# Validation regexes
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_REGEX = re.compile(r"^\+?1?[-.\ s]?\(?\d{3}\)?[-.\ s]?\d{3}[-.\ s]?\d{4}(\s*(x|ext\.?)\s*\d+)?$")
NAME_REGEX = re.compile(r"^[A-Za-z'\-\s]+(Jr\.?|III?|IV)?$", re.IGNORECASE)

VALID_POSITIONS = {"S", "OH", "RS", "MB", "DS", "L", "MH"}  # MH will be mapped to MB
STAFF_TITLES = [
    "head coach",
    "assistant",
    "associate",
    "director",
    "coordinator",
    "volunteer",
    "graduate assistant",
    "manager",
    "trainer",
    "strength",
    "conditioning",
]


def latest_export():
    """Find the most recent d1_rosters export file."""
    pattern = os.path.join(EXPORTS_DIR, "d1_rosters_*with_stats*.*")
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    if not files:
        raise SystemExit(f"No exports found matching: {pattern}")
    return files[-1]


def load_export(fn):
    """Load CSV or TSV export file."""
    if fn.endswith(".csv"):
        return pd.read_csv(fn, low_memory=False)
    return pd.read_csv(fn, sep="\t", low_memory=False)


def validate_name(name):
    """Check if name looks like a valid person name."""
    if pd.isna(name) or not name:
        return False, "missing"
    name = str(name).strip()
    # Allow 2-4 tokens
    tokens = name.split()
    if len(tokens) < 2 or len(tokens) > 5:
        return False, f"unusual_token_count ({len(tokens)})"
    # Check for digits
    if any(char.isdigit() for char in name):
        return False, "contains_digits"
    return True, "ok"


def validate_email(email):
    """Check if email format is valid."""
    if pd.isna(email) or not email:
        return False, "missing"
    email = str(email).strip()
    if not EMAIL_REGEX.match(email):
        return False, "invalid_format"
    return True, "ok"


def validate_phone(phone):
    """Check if phone number format is valid (US style)."""
    if pd.isna(phone) or not phone:
        return False, "missing"
    phone_str = str(phone).strip()
    # Unprotect Excel-wrapped values
    phone_str = excel_unprotect(phone_str)
    if not PHONE_REGEX.match(phone_str):
        return False, "invalid_format"
    return True, "ok"


def validate_title(title):
    """Check if title looks like a valid staff title."""
    if pd.isna(title) or not title:
        return False, "missing"
    title_lower = str(title).lower()
    if any(keyword in title_lower for keyword in STAFF_TITLES):
        return True, "ok"
    return False, "unrecognized_title"


def validate_position(position_raw):
    """Check if position codes are valid."""
    if pd.isna(position_raw) or not position_raw:
        return False, "missing"
    # Extract position codes
    codes = extract_position_codes(str(position_raw))
    if not codes:
        return False, "no_valid_codes"
    # Check if all codes are valid (MH is valid, will be mapped to MB elsewhere)
    invalid = [c for c in codes if c not in VALID_POSITIONS]
    if invalid:
        return False, f"invalid_codes: {','.join(invalid)}"
    return True, "ok"


def basic_validation(df):
    """Run basic validation and return summary."""
    report = {
        "file": os.path.basename(df.attrs.get("source_file", "unknown")),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": len(df),
        "team_count": df["Team"].nunique() if "Team" in df.columns else 0,
        "columns": list(df.columns),
    }

    # Check for required columns
    required_cols = ["Name", "Team", "Conference", "Position", "Class"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    report["missing_columns"] = missing_cols

    # Numeric sanity for stats columns
    stats_cols = ["Kills", "Assists", "Digs", "Blocks Per Set", "Hitting Pct"]
    for col in stats_cols:
        if col in df.columns:
            bad = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
            report[f"non_numeric_{col}"] = int(bad.sum())

    return report


def full_validation(df):
    """Run comprehensive validation and return detailed report."""
    issues = []

    # Validate player names
    if "Name" in df.columns:
        for idx, name in df["Name"].items():
            valid, reason = validate_name(name)
            if not valid:
                issues.append({
                    "row": idx,
                    "team": df.loc[idx, "Team"] if "Team" in df.columns else "",
                    "field": "Name",
                    "value": name,
                    "issue": reason,
                })

    # Validate positions
    if "Position Raw" in df.columns:
        for idx, pos in df["Position Raw"].items():
            valid, reason = validate_position(pos)
            if not valid and pd.notna(pos):
                issues.append({
                    "row": idx,
                    "team": df.loc[idx, "Team"] if "Team" in df.columns else "",
                    "field": "Position Raw",
                    "value": pos,
                    "issue": reason,
                })

    # Validate coach data (iterate through coach columns)
    for i in range(1, 6):
        name_col = f"Coach{i} Name"
        email_col = f"Coach{i} Email"
        phone_col = f"Coach{i} Phone"
        title_col = f"Coach{i} Title"

        if name_col in df.columns:
            # Only validate if name is present
            for idx, name in df[name_col].items():
                if pd.notna(name) and name:
                    # Validate email
                    if email_col in df.columns:
                        email = df.loc[idx, email_col]
                        valid, reason = validate_email(email)
                        if not valid:
                            issues.append({
                                "row": idx,
                                "team": df.loc[idx, "Team"] if "Team" in df.columns else "",
                                "field": email_col,
                                "value": email,
                                "issue": reason,
                            })

                    # Validate phone
                    if phone_col in df.columns:
                        phone = df.loc[idx, phone_col]
                        valid, reason = validate_phone(phone)
                        if not valid:
                            issues.append({
                                "row": idx,
                                "team": df.loc[idx, "Team"] if "Team" in df.columns else "",
                                "field": phone_col,
                                "value": phone,
                                "issue": reason,
                            })

                    # Validate title
                    if title_col in df.columns:
                        title = df.loc[idx, title_col]
                        valid, reason = validate_title(title)
                        if not valid:
                            issues.append({
                                "row": idx,
                                "team": df.loc[idx, "Team"] if "Team" in df.columns else "",
                                "field": title_col,
                                "value": title,
                                "issue": reason,
                            })

    # Generate summary statistics
    issue_summary = Counter(issue["issue"] for issue in issues)
    field_summary = Counter(issue["field"] for issue in issues)
    team_summary = Counter(issue["team"] for issue in issues)

    return issues, {
        "total_issues": len(issues),
        "by_issue_type": dict(issue_summary),
        "by_field": dict(field_summary),
        "by_team": dict(team_summary.most_common(20)),  # Top 20 teams with issues
    }


def write_full_report(df, issues, summary):
    """Write detailed markdown and TSV reports."""
    ts = time.strftime("%Y%m%d_%H%M%S")

    # Write issues TSV
    issues_file = os.path.join(EXPORTS_DIR, f"data_quality_issues_{ts}.tsv")
    issues_df = pd.DataFrame(issues)
    if not issues_df.empty:
        issues_df.to_csv(issues_file, sep="\t", index=False)
        print(f"Wrote issues: {issues_file}")

    # Write markdown report
    report_file = os.path.join(EXPORTS_DIR, f"data_quality_report_{ts}.md")
    with open(report_file, "w") as f:
        f.write("# Data Quality Report\n\n")
        f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\\n\n")
        f.write(f"**Export file:** {df.attrs.get('source_file', 'unknown')}\\n\n")
        f.write(f"**Total rows:** {len(df):,}\\n\n")
        f.write(f"**Total issues:** {summary['total_issues']:,}\\n\n")

        f.write("## Issues by Type\n\n")
        for issue_type, count in sorted(summary["by_issue_type"].items(), key=lambda x: -x[1]):
            f.write(f"- **{issue_type}**: {count:,}\\n")

        f.write("\\n## Issues by Field\n\n")
        for field, count in sorted(summary["by_field"].items(), key=lambda x: -x[1]):
            f.write(f"- **{field}**: {count:,}\\n")

        f.write("\\n## Top 20 Teams with Issues\n\n")
        for team, count in summary["by_team"]:
            f.write(f"- **{team}**: {count:,}\\n")

    print(f"Wrote report: {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Validate export data quality")
    parser.add_argument("--full", action="store_true", help="Run full validation with detailed report")
    args = parser.parse_args()

    fn = latest_export()
    print(f"Loading: {fn}")
    df = load_export(fn)
    df.attrs["source_file"] = fn

    # Basic validation
    report = basic_validation(df)
    ts = time.strftime("%Y%m%d_%H%M%S")
    baseline_file = os.path.join(EXPORTS_DIR, f"data_baseline_{ts}.json")
    with open(baseline_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\\nWrote baseline: {baseline_file}")
    print(f"  Rows: {report['row_count']:,}")
    print(f"  Teams: {report['team_count']}")

    # Full validation if requested
    if args.full:
        print("\\nRunning full validation...")
        issues, summary = full_validation(df)
        print(f"  Total issues: {summary['total_issues']:,}")
        write_full_report(df, issues, summary)


if __name__ == "__main__":
    main()
