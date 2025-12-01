# Browser Automation Investigation

This document covers the browser automation proof-of-concept for scraping JavaScript-rendered pages using Louisiana State University as an example.

## Background

Some volleyball team websites use JavaScript frameworks to render roster and stats data dynamically, making them inaccessible to traditional HTML parsing with BeautifulSoup. Browser automation tools like Selenium can execute JavaScript and wait for content to load before extracting data.

## Setup

### 1. Install Dependencies

```bash
# Activate your virtual environment
source venv/bin/activate

# Install browser automation packages
pip install -r requirements-browser.txt
```

This installs:
- **selenium**: Browser automation framework
- **webdriver-manager**: Automatically manages ChromeDriver installation

### 2. Verify Chrome Installation

The script uses Chrome/Chromium. Ensure you have Chrome installed:
```bash
# Check if Chrome is installed
which google-chrome || which chromium
```

## Running the PoC

### Basic Usage

```bash
# Run with visible browser (recommended for first run)
python scripts/browser_automation_poc.py
```

The script will:
1. **Analyze page structure** - Inspects the DOM to identify available selectors
2. **Scrape roster data** - Extracts player name, position, class, height
3. **Scrape stats data** - Extracts statistics tables
4. **Save outputs** - Exports data to JSON files and saves HTML source

### Outputs

The script generates several files in `exports/`:
- `lsu_roster_browser.json` - Roster data in JSON format
- `lsu_stats_browser.json` - Stats data in JSON format
- `page_source_roster.html` - Full HTML source of roster page for manual inspection

### Running Headless

Edit line 276 in `scripts/browser_automation_poc.py`:
```python
driver = setup_driver(headless=True)  # Change False to True
```

## Understanding the Code

### Key Functions

**`setup_driver(headless=True)`**
- Configures Chrome WebDriver with anti-detection measures
- Sets user agent to avoid bot blocking
- Configures window size and rendering options

**`scrape_lsu_roster(driver, year=2025)`**
- Loads roster page and waits for JavaScript to execute
- Tries multiple CSS selectors to find roster data
- Extracts player information using Selenium element finders
- Falls back to dumping page source if standard selectors fail

**`scrape_lsu_stats(driver, year=2025)`**
- Loads stats page and waits for tables to render
- Iterates through all tables on the page
- Extracts headers and data rows
- Returns structured stat dictionaries

**`analyze_page_structure(driver, url)`**
- Diagnostic function to understand page layout
- Checks for common selectors and data patterns
- Identifies embedded JSON or script-based data
- Saves full page source for manual inspection

### Selenium Basics

**Finding Elements:**
```python
# By CSS selector
element = driver.find_element(By.CSS_SELECTOR, ".player-name")
elements = driver.find_elements(By.CSS_SELECTOR, ".roster-card")

# By tag name
tables = driver.find_elements(By.TAG_NAME, "table")

# Get element text
name = element.text.strip()
```

**Waiting for Elements:**
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
element = wait.until(
    EC.presence_of_element_located((By.CSS_SELECTOR, ".roster-card"))
)
```

**Time Delays:**
```python
import time
time.sleep(2)  # Wait 2 seconds for JavaScript to finish
```

## Investigation Steps

### 1. Run the Script and Review Output

```bash
python scripts/browser_automation_poc.py
```

Look for:
- Which selectors successfully found elements
- How many roster items/stats rows were extracted
- Any error messages indicating missing elements

### 2. Inspect Page Source

Open `exports/page_source_roster.html` in a text editor and search for:
- Player names (to see how they're structured in HTML)
- Class names containing "roster", "player", "stats"
- Embedded JSON data in `<script>` tags
- Table structures

### 3. Compare with Manual Browser Inspection

1. Open https://lsusports.net/sports/womens-volleyball/roster/2025 in Chrome
2. Right-click → Inspect
3. Find a player card in the Elements tab
4. Note the class names and structure
5. Update selectors in the script if needed

### 4. Identify Data Patterns

Common patterns to look for:
- **SIDEARM platform**: `.sidearm-roster-player`, `.sidearm-roster-player-name`
- **Card-based layouts**: `.roster-card`, `.player-card`
- **Table-based layouts**: `<table>` with `<thead>` and `<tbody>`
- **JSON data**: Look for large JSON blobs in `<script type="application/json">` tags

## Customizing Selectors

If the default selectors don't work, modify `scrape_lsu_roster()`:

```python
# Example: Custom selector based on page inspection
roster_items = driver.find_elements(By.CSS_SELECTOR, ".custom-roster-class")

# Example: Different name selector
name_elem = item.find_element(By.CSS_SELECTOR, ".custom-name-class")
```

## Troubleshooting

### ChromeDriver Issues
```bash
# If webdriver-manager fails, manually install ChromeDriver
brew install chromedriver  # macOS
# Or download from https://chromedriver.chromium.org/
```

### Timeout Errors
Increase wait time in the script:
```python
wait = WebDriverWait(driver, 20)  # Increase from 10 to 20 seconds
```

### Empty Results
- Check if page requires cookies/session
- Try increasing `time.sleep()` duration
- Verify the URL is correct and loads in a regular browser
- Check for bot detection (CAPTCHA, rate limiting)

### SSL/Certificate Errors
Add to Chrome options:
```python
chrome_options.add_argument("--ignore-certificate-errors")
```

## Performance Considerations

Browser automation is **significantly slower** than HTML parsing:
- HTML parsing: ~1-2 seconds per page
- Browser automation: ~5-10 seconds per page
- For 347 teams: ~30 minutes vs. 2 hours

**Recommendations:**
1. Use browser automation **only** for JavaScript-rendered pages
2. Maintain a list of teams requiring browser automation
3. Consider caching/rate limiting to avoid detection
4. Run browser automation scrapes overnight or in batches

## Integration with Main Scraper

### Option 1: Separate Browser-Based Scraper
Create a parallel scraper for JS-rendered teams:
```
python -m src.run_scraper              # Regular teams
python -m src.run_browser_scraper      # JS-rendered teams
python -m src.merge_scraped_data       # Combine results
```

### Option 2: Hybrid Approach
Modify `team_analysis.py` to detect when HTML parsing fails and fall back to browser automation:
```python
def analyze_team(team_dict):
    try:
        # Try regular HTML parsing
        roster = parse_roster_html(html)
    except NoRosterDataFound:
        # Fall back to browser automation
        roster = scrape_with_browser(team_dict['url'])
```

### Option 3: Manual Override
Add a flag to `teams.py`:
```python
{
    "team": "Louisiana State University",
    "conference": "Southeastern Conference",
    "url": "https://lsusports.net/sports/womens-volleyball/roster",
    "stats_url": "https://lsusports.net/sports/womens-volleyball/stats/",
    "requires_browser": True  # New flag
}
```

## Next Steps

1. **Run the PoC** and review the outputs
2. **Analyze the page source** to understand LSU's specific structure
3. **Adjust selectors** based on findings
4. **Test with other problematic teams** (check validation reports for teams with missing data)
5. **Decide on integration strategy** (separate scraper vs. hybrid vs. manual)
6. **Consider alternative approaches**:
   - Check if LSU has a mobile/API endpoint with JSON data
   - Look for XML sitemaps or RSS feeds
   - Contact athletic department for data access

## Alternative: Playwright

If Selenium has issues, consider [Playwright](https://playwright.dev/python/) as an alternative:
```bash
pip install playwright
playwright install chromium
```

Playwright advantages:
- More modern API
- Better handling of modern JavaScript frameworks
- Built-in network interception
- Faster execution

## References

- [Selenium Python Documentation](https://selenium-python.readthedocs.io/)
- [WebDriver Manager](https://github.com/SergeyPirogov/webdriver_manager)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
