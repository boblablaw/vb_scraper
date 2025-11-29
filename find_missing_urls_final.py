#!/usr/bin/env python3
"""
Final manual corrections for the last 13 schools.
"""

import csv

# Manually verified URLs for the last 13 schools
FINAL_URLS = {
    "Central Connecticut State University": "https://ccsubluedevils.com/sports/wvball/roster",
    "Mercyhurst University[c]": "https://mercyhurst.edu/athletics/womens-volleyball",
    "University of New Haven": "https://newhaven.edu/athletics/womens-volleyball",
    "Saint Francis University (Saint Francis (PA))[n]": "https://sfuathletics.com/sports/womens-volleyball/roster",
    "Tennessee Technological University": "https://tntech.edu/athletics/womens-volleyball",
    "Loyola University Maryland": "https://loyolagreyhounds.com/sports/wvball/roster",
    "East Texas A&M University": "https://tamucathletics.com/sports/wvball/roster",
    "University of Texas Rio Grande Valley": "https://gorivervaqueros.com/sports/womens-volleyball/roster",
    "Jackson State University": "https://jsutigers.com/sports/womens-volleyball/roster",
    "Mississippi Valley State University": "https://mvsuathletics.com/index.aspx?path=wvball",
    "Texas Southern University": "https://tsuball.com/index.aspx?path=wvball",
    "Pepperdine University": "https://pepperdinewaves.com/sports/womens-volleyball/roster",
    "University of Texas at Arlington": "https://utamavericks.com/sports/womens-volleyball/roster",
}

def main():
    input_file = "settings/d1_wvb_programs_complete.csv"
    output_file = "settings/d1_wvb_programs_base.csv"  # Overwrite original
    
    # Read the CSV
    rows = []
    with open(input_file, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    # Update missing URLs
    missing_before = sum(1 for row in rows if not row['url'])
    print(f"Schools with missing URLs: {missing_before}")
    
    updated_count = 0
    for row in rows:
        if not row['url']:
            school = row['school']
            if school in FINAL_URLS:
                row['url'] = FINAL_URLS[school]
                print(f"✓ Updated: {school}")
                print(f"  URL: {FINAL_URLS[school]}")
                updated_count += 1
            else:
                print(f"⚠ Still missing: {school}")
    
    # Write updated CSV back to original file
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['school', 'conference', 'url', 'stats'])
        writer.writeheader()
        writer.writerows(rows)
    
    missing_after = sum(1 for row in rows if not row['url'])
    
    print(f"\n=== FINAL SUMMARY ===")
    print(f"Total schools: {len(rows)}")
    print(f"Missing before: {missing_before}")
    print(f"Updated: {updated_count}")
    print(f"Missing after: {missing_after}")
    print(f"\nUpdated CSV saved to: {output_file}")

if __name__ == "__main__":
    main()
