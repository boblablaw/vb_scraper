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


def dismiss_cookie_popup(driver):
    """Try to dismiss cookie consent popup if present."""
    try:
        # Common cookie popup button selectors
        cookie_selectors = [
            "button[id*='accept']",
            "button[id*='consent']",
            "button.accept",
            "a.accept",
            "#onetrust-accept-btn-handler",
            "button.css-47sehv",  # Common CSS class for accept buttons
        ]
        
        for selector in cookie_selectors:
            try:
                button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                button.click()
                print("✓ Dismissed cookie popup")
                time.sleep(1)
                return True
            except:
                continue
        
        return False
    except Exception as e:
        return False


def scrape_lsu_roster(driver, year=2025):
    """
    Scrape roster data from LSU volleyball roster page.
    
    Returns:
        list: Player dictionaries with name, position, class, height
    """
    url = "https://lsusports.net/sports/vb/roster/"
    print(f"Fetching roster from: {url}")
    
    driver.get(url)
    
    # Dismiss cookie popup if present
    dismiss_cookie_popup(driver)
    
    # Wait for roster content to load
    try:
        wait = WebDriverWait(driver, 15)
        
        # Wait for the players-table to be present
        wait.until(EC.presence_of_element_located((By.ID, "players-table")))
        print("Found roster table: #players-table")
        
        # Wait for table rows to be populated (DataTables might load asynchronously)
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#players-table tbody tr")) > 0)
        
        # Additional wait for JavaScript to finish rendering
        time.sleep(3)
        
        players = []
        
        # Find the players table
        table = driver.find_element(By.ID, "players-table")
        
        # Get table rows
        tbody = table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        print(f"Found {len(rows)} roster rows")
        
        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                
                # Debug: print cell count for first few rows
                if idx < 3:
                    print(f"  Row {idx}: {len(cells)} cells")
                    if cells:
                        print(f"    First cell text: '{cells[0].text[:50]}'")
                
                if not cells or len(cells) < 5:
                    if idx < 3:
                        print(f"    Skipping - not enough cells")
                    continue
                
                player = {}
                
                # Table structure: [Number, Name, Position, Height, Class, Experience, Hometown, HS, Previous]
                # Cell 0: Jersey number
                # Cell 1: Name (may be nested in a div/link)
                # Cell 2: Position
                # Cell 3: Height
                # Cell 4: Class
                
                # Extract name - use innerText for DataTables compatibility
                name_text = cells[1].get_attribute('innerText').strip() if cells[1].get_attribute('innerText') else ''
                # Remove pronunciation icon text if present
                if "Hear how to pronounce" in name_text:
                    name_text = name_text.split("Hear how to pronounce")[0].strip()
                player["name"] = name_text
                
                player["position"] = cells[2].get_attribute('innerText').strip() if cells[2].get_attribute('innerText') else ''
                player["height"] = cells[3].get_attribute('innerText').strip() if cells[3].get_attribute('innerText') else ''
                player["class"] = cells[4].get_attribute('innerText').strip() if cells[4].get_attribute('innerText') else ''
                
                if player["name"]:
                    players.append(player)
                else:
                    if idx < 3:
                        print(f"    Skipping - no name found")
                    
            except Exception as e:
                print(f"Error parsing roster row {idx}: {e}")
                continue
        
        # If no players found, dump page source for analysis
        if not players:
            print("\nNo players found in table.")
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
    url = f"https://lsusports.net/sports/vb/cumestats/"
    print(f"\nFetching stats from: {url}")
    
    driver.get(url)
    
    # Dismiss cookie popup if present
    dismiss_cookie_popup(driver)
    
    try:
        # Wait for stats table to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".advanced-table__table")))
        print("Found stats table: .advanced-table__table")
        
        # Wait for table to be populated
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".advanced-table__table tbody tr")) > 0)
        
        time.sleep(3)
        
        # Find stats tables with the specific class
        tables = driver.find_elements(By.CSS_SELECTOR, ".advanced-table__table")
        print(f"Found {len(tables)} stats table(s)")
        
        stats = []
        
        for idx, table in enumerate(tables):
            try:
                rows_count = len(table.find_elements(By.TAG_NAME, 'tr'))
                print(f"\nTable {idx + 1}: {rows_count} rows")
                
                # Get headers - use innerText for DataTables compatibility
                headers = []
                try:
                    header_row = table.find_element(By.TAG_NAME, "thead")
                    header_cells = header_row.find_elements(By.TAG_NAME, "th")
                    headers = [cell.get_attribute('innerText').strip() if cell.get_attribute('innerText') else cell.text.strip() for cell in header_cells]
                    print(f"  Headers: {headers[:10]}")  # Show first 10 headers
                except Exception as e:
                    print(f"  Warning: Could not extract headers: {e}")
                    continue
                
                # Get data rows
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                
                print(f"  Processing {len(rows)} data rows...")
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        # Use innerText instead of text for DataTables compatibility
                        row_data = {
                            headers[i]: cells[i].get_attribute('innerText').strip() if cells[i].get_attribute('innerText') else ''
                            for i in range(min(len(headers), len(cells)))
                        }
                        
                        # Debug first few rows
                        if row_idx < 2:
                            print(f"    Row {row_idx} sample: {list(row_data.items())[:3]}")
                        
                        stats.append(row_data)
                
                print(f"  Extracted {len(rows)} stat rows from table {idx + 1}")
                
            except Exception as e:
                print(f"  Error parsing table {idx + 1}: {e}")
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
    # Extract a meaningful name from URL
    url_parts = [p for p in url.rstrip('/').split('/') if p]
    page_name = url_parts[-1] if url_parts else "page"
    output_file = f"exports/page_source_{page_name}.html"
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
        
        # Analyze roster page structure first
        analyze_page_structure(driver, "https://lsusports.net/sports/vb/roster/")
        
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
        
        # Analyze stats page structure
        analyze_page_structure(driver, "https://lsusports.net/sports/vb/cumestats/")
        
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
