#!/usr/bin/env python3
"""
Third pass with corrected URLs for the remaining 25 schools.
"""

import csv
import time
import requests

# Corrected URLs for remaining schools
CORRECTED_URLS = {
    "Central Connecticut State University": "https://ccsubluedevils.com/sports/womens-volleyball/roster",
    "Mercyhurst University[c]": "https://mercyhurstathletics.com/sports/womens-volleyball/roster",
    "University of New Haven": "https://newhavenathletics.com/sports/womens-volleyball/roster",
    "Saint Francis University (Saint Francis (PA))[n]": "https://sfuredflash.com/sports/womens-volleyball/roster",
    "Tennessee Technological University": "https://ttusports.com/sports/womens-volleyball/roster",
    "American University": "https://aueagles.com/sports/womens-volleyball/roster",
    "Bucknell University": "https://bucknellbison.com/sports/womens-volleyball/roster",
    "Loyola University Maryland": "https://loyolagreyhounds.com/sports/womens-volleyball/roster",
    "Auburn University": "https://auburntigers.com/sports/womens-volleyball/roster",
    "Louisiana State University": "https://lsusports.net/sports/womens-volleyball/roster",
    "Mississippi State University": "https://hailstate.com/sports/womens-volleyball/roster",
    "University of Mississippi (Ole Miss)": "https://olemisssports.com/sports/womens-volleyball/roster",
    "Texas A&M University": "https://12thman.com/sports/womens-volleyball/roster",
    "University of Tennessee at Chattanooga": "https://gomocs.com/sports/womens-volleyball/roster",
    "East Tennessee State University": "https://etsubucs.com/sports/womens-volleyball/roster",
    "University of North Carolina at Greensboro": "https://uncgspartans.com/sports/womens-volleyball/roster",
    "Western Carolina University": "https://catamountsports.com/sports/womens-volleyball/roster",
    "Wofford College": "https://woffordterriers.com/sports/womens-volleyball/roster",
    "East Texas A&M University": "https://tamucathletics.com/sports/womens-volleyball/roster",
    "University of Texas Rio Grande Valley": "https://govaqueros.com/sports/womens-volleyball/roster",
    "Jackson State University": "https://jsumtigers.com/sports/womens-volleyball/roster",
    "Mississippi Valley State University": "https://mvsuathletics.com/sports/womens-volleyball/roster",
    "Texas Southern University": "https://tsuball.com/sports/womens-volleyball/roster",
    "Pepperdine University": "https://pepperdinesports.com/sports/womens-volleyball/roster",
    "University of Texas at Arlington": "https://utamavs.com/sports/womens-volleyball/roster",
}

def check_url(url):
    """Check if a URL exists and returns 200."""
    try:
        response = requests.get(url, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except Exception as e:
        print(f"    Error: {e}")
        return False

def main():
    input_file = "settings/d1_wvb_programs_final.csv"
    output_file = "settings/d1_wvb_programs_complete.csv"
    
    # Read the CSV
    rows = []
    with open(input_file, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    # Find and update missing URLs
    missing_count = sum(1 for row in rows if not row['url'])
    print(f"Found {missing_count} schools still missing URLs")
    
    found_count = 0
    failed = []
    for i, row in enumerate(rows, 1):
        if not row['url']:
            school = row['school']
            print(f"\n[{i}/{len(rows)}] {school}")
            
            if school in CORRECTED_URLS:
                url = CORRECTED_URLS[school]
                print(f"  Trying: {url}")
                if check_url(url):
                    print(f"  ✓ CONFIRMED")
                    row['url'] = url
                    found_count += 1
                else:
                    print(f"  ✗ FAILED - URL doesn't work")
                    failed.append((school, url))
                time.sleep(0.5)
            else:
                print(f"  ⚠ No URL mapping found")
                failed.append((school, "NO MAPPING"))
    
    # Write updated CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['school', 'conference', 'url', 'stats'])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n\n=== SUMMARY ===")
    print(f"Total schools: {len(rows)}")
    print(f"Missing URLs (before): {missing_count}")
    print(f"Found URLs: {found_count}")
    print(f"Still missing: {missing_count - found_count}")
    
    if failed:
        print(f"\n=== FAILED/MISSING ({len(failed)}) ===")
        for school, url in failed:
            print(f"  - {school}: {url}")
    
    print(f"\nComplete CSV saved to: {output_file}")

if __name__ == "__main__":
    main()
