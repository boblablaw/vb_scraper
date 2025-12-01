#!/usr/bin/env python3
"""
Second pass to find remaining missing URLs with manual overrides for difficult schools.
"""

import csv
import time
import requests

# Manual URL mappings for schools with non-standard patterns
MANUAL_URLS = {
    "San Diego State University": "https://goaztecs.com/sports/womens-volleyball/roster",
    "San Jose State University": "https://sjsuspartans.com/sports/womens-volleyball/roster",
    "Central Connecticut State University": "https://ccsubluedevils.com/sports/womens-volleyball/roster",
    "Chicago State University": "https://csucougars.com/sports/womens-volleyball/roster",
    "Fairleigh Dickinson University": "https://fduknights.com/sports/womens-volleyball/roster",
    "Long Island University (LIU)": "https://liusharks.com/sports/womens-volleyball/roster",
    "Mercyhurst University[c]": "https://mercyhurstathletics.com/sports/womens-volleyball/roster",
    "University of New Haven": "https://newhavenathletics.com/sports/womens-volleyball/roster",
    "Saint Francis University (Saint Francis (PA))[n]": "https://sfuredflash.com/sports/womens-volleyball/roster",
    "Stonehill College": "https://stonehillskyhawks.com/sports/womens-volleyball/roster",
    "Eastern Illinois University": "https://eiupanthers.com/sports/womens-volleyball/roster",
    "Lindenwood University": "https://lindenwoodlions.com/sports/womens-volleyball/roster",
    "University of Arkansas at Little Rock (Little Rock)": "https://lrtrojans.com/sports/womens-volleyball/roster",
    "Morehead State University": "https://msueagles.com/sports/womens-volleyball/roster",
    "Southern Illinois University Edwardsville": "https://siuecougars.com/sports/womens-volleyball/roster",
    "Southeast Missouri State University": "https://gosoutheast.com/sports/womens-volleyball/roster",
    "University of Southern Indiana": "https://gousieagles.com/sports/womens-volleyball/roster",
    "Tennessee State University": "https://tsutigers.com/sports/womens-volleyball/roster",
    "Tennessee Technological University": "https://ttusports.com/sports/womens-volleyball/roster",
    "University of Tennessee at Martin (UT Martin)": "https://utmsports.com/sports/womens-volleyball/roster",
    "Western Illinois University": "https://goleathernecks.com/sports/womens-volleyball/roster",
    "United States Military Academy": "https://goarmywestpoint.com/sports/womens-volleyball/roster",
    "United States Naval Academy": "https://navysports.com/sports/womens-volleyball/roster",
    "The Citadel": "https://citadelsports.com/sports/womens-volleyball/roster",
    "East Texas A&M University": "https://tamucathletics.com/sports/womens-volleyball/roster",
    "Houston Christian University": "https://hbuhuskies.com/sports/womens-volleyball/roster",
    "University of the Incarnate Word": "https://uiwcardinals.com/sports/womens-volleyball/roster",
    "Lamar University": "https://lamarcardinals.com/sports/womens-volleyball/roster",
    "McNeese State University": "https://mcneesesports.com/sports/womens-volleyball/roster",
    "University of New Orleans": "https://unoprivateers.com/sports/womens-volleyball/roster",
    "Nicholls State University": "https://geauxcolonels.com/sports/womens-volleyball/roster",
    "Northwestern State University": "https://nsudemons.com/sports/womens-volleyball/roster",
    "Southeastern Louisiana University": "https://lionsports.net/sports/womens-volleyball/roster",
    "Stephen F. Austin State University": "https://sfajacks.com/sports/womens-volleyball/roster",
    "Texas A&M University-Corpus Christi": "https://goislanders.com/sports/womens-volleyball/roster",
    "University of Texas Rio Grande Valley": "https://govaqueros.com/sports/womens-volleyball/roster",
    "Alabama A&M University": "https://aamusports.com/sports/womens-volleyball/roster",
    "Alabama State University": "https://bamastatesports.com/sports/womens-volleyball/roster",
    "Alcorn State University": "https://alcornsports.com/sports/womens-volleyball/roster",
    "Bethune–Cookman University": "https://bcuathletics.com/sports/womens-volleyball/roster",
    "Florida A&M University": "https://famuathletics.com/sports/womens-volleyball/roster",
    "Grambling State University": "https://gsutigers.com/sports/womens-volleyball/roster",
    "Jackson State University": "https://jsumtigers.com/sports/womens-volleyball/roster",
    "Mississippi Valley State University": "https://mvsuathletics.com/sports/womens-volleyball/roster",
    "Prairie View A&M University": "https://pvpanthers.com/sports/womens-volleyball/roster",
    "Southern University": "https://gojagsports.com/sports/womens-volleyball/roster",
    "Texas Southern University": "https://tsuball.com/sports/womens-volleyball/roster",
    "University of Denver": "https://denverpioneers.com/sports/womens-volleyball/roster",
    "University of Missouri-Kansas City": "https://gokangaroos.com/sports/womens-volleyball/roster",
    "University of North Dakota": "https://fightinghawks.com/sports/womens-volleyball/roster",
    "North Dakota State University": "https://gobison.com/sports/womens-volleyball/roster",
    "University of Nebraska Omaha": "https://omavs.com/sports/womens-volleyball/roster",
    "Oral Roberts University": "https://oruathletics.com/sports/womens-volleyball/roster",
    "University of St. Thomas": "https://tommiesports.com/sports/womens-volleyball/roster",
    "University of South Dakota": "https://coyotes.com/sports/womens-volleyball/roster",
    "South Dakota State University": "https://gojacks.com/sports/womens-volleyball/roster",
    "Appalachian State University": "https://appstatesports.com/sports/womens-volleyball/roster",
    "Arkansas State University": "https://astateredwolves.com/sports/womens-volleyball/roster",
    "Coastal Carolina University": "https://goccusports.com/sports/womens-volleyball/roster",
    "Georgia Southern University": "https://gseagles.com/sports/womens-volleyball/roster",
    "Georgia State University": "https://georgiastatesports.com/sports/womens-volleyball/roster",
    "James Madison University": "https://jmusports.com/sports/womens-volleyball/roster",
    "University of Louisiana at Lafayette": "https://ragincajuns.com/sports/womens-volleyball/roster",
    "Marshall University": "https://herdzone.com/sports/womens-volleyball/roster",
    "Old Dominion University": "https://odusports.com/sports/womens-volleyball/roster",
    "University of South Alabama": "https://usajaguars.com/sports/womens-volleyball/roster",
    "The University of Southern Mississippi": "https://southernmiss.com/sports/womens-volleyball/roster",
    "Texas State University": "https://txstatebobcats.com/sports/womens-volleyball/roster",
    "Troy University": "https://troytrojans.com/sports/womens-volleyball/roster",
    "University of Louisiana at Monroe": "https://ulmwarhawks.com/sports/womens-volleyball/roster",
    "Gonzaga University": "https://gozags.com/sports/womens-volleyball/roster",
    "Loyola Marymount University": "https://lmulions.com/sports/womens-volleyball/roster",
    "Oregon State University": "https://osubeavers.com/sports/womens-volleyball/roster",
    "University of the Pacific": "https://pacifictigers.com/sports/womens-volleyball/roster",
    "Pepperdine University": "https://pepperdinesports.com/sports/womens-volleyball/roster",
    "University of Portland": "https://portlandpilots.com/sports/womens-volleyball/roster",
    "University of San Diego": "https://usdtoreros.com/sports/womens-volleyball/roster",
    "University of San Francisco": "https://usfdons.com/sports/womens-volleyball/roster",
    "Santa Clara University": "https://santaclarabroncos.com/sports/womens-volleyball/roster",
    "Saint Mary's College of California": "https://smcgaels.com/sports/womens-volleyball/roster",
    "Seattle University": "https://goseattleu.com/sports/womens-volleyball/roster",
    "Washington State University": "https://wsucougars.com/sports/womens-volleyball/roster",
    "Abilene Christian University": "https://acusports.com/sports/womens-volleyball/roster",
    "California Baptist University": "https://cbulancers.com/sports/womens-volleyball/roster",
    "Southern Utah University": "https://suutbirds.com/sports/womens-volleyball/roster",
    "Tarleton State University": "https://tarletonsports.com/sports/womens-volleyball/roster",
    "University of Texas at Arlington": "https://utamavs.com/sports/womens-volleyball/roster",
    "Utah Tech University": "https://utahtech.edu/athletics/sports/womens-volleyball/roster",
    "Utah Valley University": "https://gouvu.com/sports/womens-volleyball/roster",
}

def check_url(url):
    """Check if a URL exists and returns 200."""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return True
        response = requests.get(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def main():
    input_file = "settings/d1_wvb_programs_updated.csv"
    output_file = "settings/d1_wvb_programs_final.csv"
    
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
    for i, row in enumerate(rows, 1):
        if not row['url']:
            school = row['school']
            print(f"\n[{i}/{len(rows)}] {school}")
            
            if school in MANUAL_URLS:
                url = MANUAL_URLS[school]
                print(f"  Using manual URL: {url}")
                if check_url(url):
                    print(f"  ✓ CONFIRMED")
                    row['url'] = url
                    found_count += 1
                else:
                    print(f"  ✗ FAILED - URL doesn't work")
                time.sleep(0.5)
    
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
    print(f"\nFinal CSV saved to: {output_file}")

if __name__ == "__main__":
    main()
