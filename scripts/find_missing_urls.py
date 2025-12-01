#!/usr/bin/env python3
"""
Script to find missing roster URLs for D1 women's volleyball programs.
Reads d1_wvb_programs_base.csv and attempts to find roster URLs for schools with empty URL fields.
"""

import csv
import time
import requests
from urllib.parse import quote_plus

# Common athletic department URL patterns
COMMON_PATTERNS = [
    # SIDEARM patterns
    "go{school}.com/sports/womens-volleyball/roster",
    "go{school}.com/sports/volleyball/roster", 
    "{school}athletics.com/sports/womens-volleyball/roster",
    "{school}sports.com/sports/womens-volleyball/roster",
    "{school}sports.com/sports/wvball/roster",
    # Presto patterns
    "{school}athletics.com/roster.aspx?path=wvball",
    "go{school}.com/roster.aspx?path=wvball",
    # Other patterns
    "{school}.edu/athletics/womens-volleyball/roster",
    "www.{school}athletics.com/sports/womens-volleyball/roster",
    # Additional patterns
    "{school}aztecs.com/sports/womens-volleyball/roster",
    "{school}spartans.com/sports/womens-volleyball/roster",
    "{school}eagles.com/sports/womens-volleyball/roster",
    "{school}redbirds.com/sports/womens-volleyball/roster",
    "{school}tigers.com/sports/womens-volleyball/roster",
    "{school}lions.com/sports/womens-volleyball/roster",
    "www.{school}athletics.com/roster.aspx?path=wvball",
    "{school}.edu/sports/womens-volleyball/roster",
    "{school}athletics.com/roster.aspx?path=volleyball",
    "{school}athletics.com/sports/volleyball/roster",
]

def normalize_school_for_url(school_name):
    """Convert school name to common URL formats."""
    # Remove common words
    name = school_name.lower()
    name = name.replace("university of ", "")
    name = name.replace("university ", "")
    name = name.replace("college of ", "")
    name = name.replace("college ", "")
    name = name.replace("the ", "")
    name = name.replace(" university", "")
    name = name.replace(" college", "")
    name = name.replace(" state", "state")
    name = name.replace(" & ", "")
    name = name.replace("&", "")
    name = name.replace(" ", "")
    name = name.replace("-", "")
    name = name.replace("'", "")
    name = name.replace(".", "")
    name = name.replace(",", "")
    name = name.replace("(", "")
    name = name.replace(")", "")
    name = name.replace("[", "")
    name = name.replace("]", "")
    
    return name

def check_url(url):
    """Check if a URL exists and returns 200."""
    try:
        response = requests.head(f"https://{url}", timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return True
        # Try GET if HEAD fails
        response = requests.get(f"https://{url}", timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def find_roster_url(school_name):
    """Try to find the roster URL for a school."""
    normalized = normalize_school_for_url(school_name)
    
    print(f"\nSearching for: {school_name}")
    print(f"  Normalized: {normalized}")
    
    # Try common patterns
    for pattern in COMMON_PATTERNS:
        url = pattern.format(school=normalized)
        print(f"  Trying: https://{url}")
        if check_url(url):
            print(f"  ✓ FOUND: https://{url}")
            return f"https://{url}"
        time.sleep(0.5)  # Be polite
    
    print(f"  ✗ Not found")
    return None

def main():
    input_file = "settings/d1_wvb_programs_base.csv"
    output_file = "settings/d1_wvb_programs_updated.csv"
    
    # Read the CSV
    rows = []
    with open(input_file, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    # Find missing URLs
    missing_count = sum(1 for row in rows if not row['url'])
    print(f"Found {missing_count} schools with missing URLs")
    
    found_count = 0
    for i, row in enumerate(rows, 1):
        if not row['url']:
            print(f"\n[{i}/{len(rows)}] {row['school']}")
            url = find_roster_url(row['school'])
            if url:
                row['url'] = url
                found_count += 1
            time.sleep(1)  # Be polite between schools
    
    # Write updated CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['school', 'conference', 'url', 'stats'])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n\n=== SUMMARY ===")
    print(f"Total schools: {len(rows)}")
    print(f"Missing URLs: {missing_count}")
    print(f"Found URLs: {found_count}")
    print(f"Still missing: {missing_count - found_count}")
    print(f"\nUpdated CSV saved to: {output_file}")

if __name__ == "__main__":
    main()
