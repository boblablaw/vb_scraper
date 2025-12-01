#!/usr/bin/env python3
"""
Browser automation proof-of-concept for scraping JavaScript-rendered pages.

This script demonstrates how to use Selenium to scrape roster and stats data
from Louisiana State University as an example.

Requirements:
    pip install selenium webdriver-manager

Usage:
    python scripts/browser_automation_poc.py
"""

import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def setup_driver(headless=True):
    """Set up Chrome WebDriver with appropriate options."""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless=new")
    
    # Additional options for stability
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # User agent to avoid bot detection
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    
    return driver


def scrape_lsu_roster(driver, year=2025):
    """
    Scrape roster data from LSU volleyball roster page.
    
    Returns:
        list: Player dictionaries with name, position, class, height
    """
    url = f"https://lsusports.net/sports/womens-volleyball/roster/{year}"
    print(f"Fetching roster from: {url}")
    
    driver.get(url)
    
    # Wait for roster content to load
    try:
        # Try multiple possible selectors
        wait = WebDriverWait(driver, 10)
        
        # Common SIDEARM roster selectors
        selectors_to_try = [
            ".sidearm-roster-players",
            ".sidearm-roster-player",
            ".roster-card",
            "[class*='roster']",
        ]
        
        for selector in selectors_to_try:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                print(f"Found roster content with selector: {selector}")
                break
            except:
                continue
        
        # Additional wait for JavaScript to finish rendering
        time.sleep(2)
        
        players = []
        
        # Try to find roster cards/items
        roster_items = driver.find_elements(By.CSS_SELECTOR, ".sidearm-roster-player")
        
        if not roster_items:
            # Fallback: try other common patterns
            roster_items = driver.find_elements(By.CSS_SELECTOR, "[class*='roster-card']")
        
        print(f"Found {len(roster_items)} roster items")
        
        for item in roster_items:
            try:
                player = {}
                
                # Extract name
                name_elem = item.find_element(By.CSS_SELECTOR, ".sidearm-roster-player-name, h3, .name")
                player["name"] = name_elem.text.strip()
                
                # Extract position
                try:
                    pos_elem = item.find_element(By.CSS_SELECTOR, ".sidearm-roster-player-position, .position")
                    player["position"] = pos_elem.text.strip()
                except:
                    player["position"] = ""
                
                # Extract class year
                try:
                    class_elem = item.find_element(By.CSS_SELECTOR, ".sidearm-roster-player-academic-year, .year, .class")
                    player["class"] = class_elem.text.strip()
                except:
                    player["class"] = ""
                
                # Extract height
                try:
                    height_elem = item.find_element(By.CSS_SELECTOR, ".sidearm-roster-player-height, .height")
                    player["height"] = height_elem.text.strip()
                except:
                    player["height"] = ""
                
                if player["name"]:
                    players.append(player)
                    
            except Exception as e:
                print(f"Error parsing roster item: {e}")
                continue
        
        # If structured approach fails, dump page source for analysis
        if not players:
            print("\nNo players found with standard selectors.")
            print("Dumping page source snippet for analysis:\n")
            page_source = driver.page_source
            print(page_source[:2000])
            print("\n[... page source truncated ...]\n")
        
        return players
        
    except Exception as e:
        print(f"Error loading roster page: {e}")
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        return []


def scrape_lsu_stats(driver, year=2025):
    """
    Scrape statistics from LSU volleyball stats page.
    
    Returns:
        list: Player stat dictionaries
    """
    url = f"https://lsusports.net/sports/womens-volleyball/stats/{year}"
    print(f"\nFetching stats from: {url}")
    
    driver.get(url)
    
    try:
        # Wait for stats table to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table, .stats-table")))
        
        time.sleep(2)
        
        # Try to find stats tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"Found {len(tables)} tables on stats page")
        
        stats = []
        
        for idx, table in enumerate(tables):
            try:
                print(f"\nTable {idx + 1}:")
                print(f"  Rows: {len(table.find_elements(By.TAG_NAME, 'tr'))}")
                
                # Get headers
                headers = []
                header_row = table.find_element(By.TAG_NAME, "thead")
                header_cells = header_row.find_elements(By.TAG_NAME, "th")
                headers = [cell.text.strip() for cell in header_cells]
                print(f"  Headers: {headers[:10]}")  # Show first 10 headers
                
                # Get data rows
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        row_data = {
                            headers[i]: cells[i].text.strip() 
                            for i in range(min(len(headers), len(cells)))
                        }
                        stats.append(row_data)
                
            except Exception as e:
                print(f"  Error parsing table: {e}")
                continue
        
        return stats
        
    except Exception as e:
        print(f"Error loading stats page: {e}")
        print(f"Page title: {driver.title}")
        return []


def analyze_page_structure(driver, url):
    """
    Analyze page structure to understand DOM layout.
    Useful for debugging when standard selectors don't work.
    """
    print(f"\n=== Analyzing page structure: {url} ===\n")
    driver.get(url)
    
    # Wait for page to load
    time.sleep(3)
    
    print(f"Page title: {driver.title}")
    print(f"Current URL: {driver.current_url}")
    
    # Check for common roster/stats containers
    selectors_to_check = [
        ".sidearm-roster-players",
        ".sidearm-roster-player",
        ".roster-card",
        "[class*='roster']",
        "table",
        ".stats-table",
        "[id*='roster']",
        "[id*='stats']",
    ]
    
    print("\nChecking for common selectors:")
    for selector in selectors_to_check:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"  ✓ {selector}: {len(elements)} element(s)")
            else:
                print(f"  ✗ {selector}: not found")
        except Exception as e:
            print(f"  ✗ {selector}: error - {e}")
    
    # Check for scripts/JSON data
    print("\nLooking for embedded data:")
    scripts = driver.find_elements(By.TAG_NAME, "script")
    print(f"  Found {len(scripts)} script tags")
    
    for idx, script in enumerate(scripts[:5]):  # Check first 5
        content = script.get_attribute("innerHTML")
        if content and ("roster" in content.lower() or "player" in content.lower()):
            print(f"  Script {idx} contains roster/player data (length: {len(content)})")
    
    # Save full page source for detailed analysis
    output_file = f"exports/page_source_{url.split('/')[-2]}.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"\nFull page source saved to: {output_file}")


def main():
    """Main execution function."""
    print("=== Browser Automation PoC for LSU Volleyball ===\n")
    
    driver = None
    try:
        # Set up driver
        print("Setting up Chrome WebDriver...")
        driver = setup_driver(headless=False)  # Set to False to see browser
        print("✓ Driver ready\n")
        
        # Analyze page structure first
        analyze_page_structure(driver, "https://lsusports.net/sports/womens-volleyball/roster/2025")
        
        # Scrape roster
        print("\n" + "="*60)
        roster = scrape_lsu_roster(driver)
        
        if roster:
            print(f"\n✓ Successfully scraped {len(roster)} players")
            print("\nSample players:")
            for player in roster[:3]:
                print(f"  - {player}")
            
            # Save roster to JSON
            with open("exports/lsu_roster_browser.json", "w") as f:
                json.dump(roster, f, indent=2)
            print("\n✓ Roster saved to exports/lsu_roster_browser.json")
        else:
            print("\n✗ No roster data found")
        
        # Scrape stats
        print("\n" + "="*60)
        stats = scrape_lsu_stats(driver)
        
        if stats:
            print(f"\n✓ Successfully scraped {len(stats)} stat entries")
            print("\nSample stats:")
            for stat in stats[:3]:
                print(f"  - {stat}")
            
            # Save stats to JSON
            with open("exports/lsu_stats_browser.json", "w") as f:
                json.dump(stats, f, indent=2)
            print("\n✓ Stats saved to exports/lsu_stats_browser.json")
        else:
            print("\n✗ No stats data found")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            print("\nClosing browser...")
            driver.quit()
            print("✓ Done")


if __name__ == "__main__":
    main()
