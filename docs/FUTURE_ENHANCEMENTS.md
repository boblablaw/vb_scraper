# Future Enhancements - Volleyball Scraper

## Current Status

**Coverage**: 305 of 347 teams (87.9%)  
**Missing**: 42 teams (12.1%)

## Remaining Teams by Fix Complexity

### 🔴 HIGH COMPLEXITY: JavaScript-Rendered Sites (28 teams)

**Requires**: Browser automation (Selenium/Playwright)  
**Estimated Effort**: 12-16 hours  
**Maintenance**: High (requires browser driver management)

#### SEC Schools (12 teams) - All use JavaScript rendering
- University of Alabama
- University of Arkansas  
- University of Florida
- University of Georgia
- University of Kentucky
- Louisiana State University
- University of Missouri
- University of Oklahoma
- University of South Carolina
- University of Tennessee
- University of Texas
- Vanderbilt University

**Pattern**: All redirect to `/lander` page with 114-byte JavaScript redirect
**URLs work**: Yes, but content is client-side rendered
**Solution**: Selenium with headless Chrome or Playwright

#### WCC & Other Conferences (16 teams) - JavaScript rendering
- Gonzaga University
- University of Portland
- University of San Diego
- University of San Francisco
- Santa Clara University
- Seattle University
- Washington State University
- University of Denver
- University of North Dakota
- University of South Dakota
- University of St. Thomas
- Lafayette College
- Long Island University (LIU)
- Lamar University
- University of New Orleans
- Furman University
- Mercer University

**Pattern**: Same 114-byte JavaScript redirect
**Solution**: Same as SEC schools

---

### 🟡 MEDIUM COMPLEXITY: Parseable HTML (7-10 teams)

**Requires**: Custom parser development  
**Estimated Effort**: 3-4 hours  
**Maintenance**: Low

#### Confirmed Parseable
1. **University of the Pacific** (44KB HTML)
2. **Oregon State University** (3KB HTML)
3. **James Madison University** (113KB HTML)
4. **The Citadel** (44KB HTML)
5. **Utah Tech University** (44KB HTML)
6. **Troy University** (792KB HTML) - May also use s-person-details

#### Possibly Parseable (need investigation)
- Utah State University (small redirect, but might have alternate URL)

**Next Steps**:
1. Analyze HTML structure in `fixtures/html/` for each team
2. Identify common patterns (likely SIDEARM variants or custom platforms)
3. Implement 1-2 new parsers to cover these patterns
4. Test and validate

---

### 🔴 LOW PRIORITY: Infrastructure Issues (5-7 teams)

**Requires**: Manual investigation, domain changes  
**Estimated Effort**: 1-2 hours  
**Maintenance**: Medium

#### Confirmed Issues
- **University of New Mexico** - Domain parking page (gonewmexico.com)
- **University of Wyoming** - Empty page (gowyoming.com)
- **Central Connecticut State University** - 404 or bot protection
- **Tennessee Technological University** - 404 or bot protection

#### Possible Issues
- **Mississippi Valley State** (may need URL verification)
- **University of Idaho** (SSL certificate issues)

**Next Steps**:
1. Contact athletic departments or check for new domains
2. Look for alternate roster URLs (PDF rosters, archive.org, etc.)
3. Document as permanently unavailable if domains are down

---

## Implementation Roadmap

### Phase 1: Quick Wins (3-4 hours)
**Goal**: Fix 7-10 parseable HTML teams → 90% coverage

**Tasks**:
1. Analyze `fixtures/html/` for Pacific, Oregon State, JMU, Citadel, Utah Tech
2. Identify 1-2 new parsing patterns
3. Implement new parsers in `roster.py`
4. Test with `python run_scraper.py --team "Team Name"`
5. Validate data quality

**Expected Outcome**: 312-315 teams (90-91% coverage)

---

### Phase 2: Browser Automation (12-16 hours)
**Goal**: Fix 28 JavaScript-rendered teams → 98% coverage

**Tasks**:

#### 2.1 Setup (2 hours)
- Install Selenium or Playwright
- Configure headless browser
- Create new module `browser_scraper.py`
- Test with one SEC school

#### 2.2 Implementation (6-8 hours)
```python
# browser_scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def fetch_html_with_browser(url, timeout=10):
    """Fetch JavaScript-rendered HTML using Selenium."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        # Wait for roster content to load
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, 
                'a[href*="/roster/"]')) > 5
        )
        html = driver.page_source
        return html
    finally:
        driver.quit()
```

- Modify `utils.py` to detect JS redirects
- Add fallback to browser scraping
- Test with all 28 teams
- Handle rate limiting and timeouts

#### 2.3 Optimization (2-3 hours)
- Implement caching (save rendered HTML to `fixtures/`)
- Add browser pool for parallel scraping
- Error handling and retry logic
- Update documentation

#### 2.4 Testing & Validation (2-3 hours)
- Validate all 28 teams parse correctly
- Check data quality
- Performance testing
- Update team-specific notes in `settings/`

**Expected Outcome**: 333-338 teams (96-97% coverage)

**Dependencies**:
```bash
pip install selenium
# OR
pip install playwright
playwright install chromium
```

---

### Phase 3: Infrastructure Fixes (1-2 hours)
**Goal**: Investigate and document permanently unavailable teams

**Tasks**:
1. Research new domains for Wyoming, New Mexico, etc.
2. Update URLs in `settings/teams_urls.py` if found (base URLs without year)
3. Update `KNOWN_LIMITATIONS.md` documenting unavailable teams
4. Add skip logic in scraper for documented failures

**Expected Outcome**: 335-340 teams (96.5-98% coverage)

---

## Recommended Priority Order

### Option A: Maximum Coverage (16-20 hours total)
1. Phase 1: Parseable HTML (3-4 hours) → 90% coverage
2. Phase 2: Browser automation (12-16 hours) → 98% coverage  
3. Phase 3: Infrastructure (1-2 hours) → Final documentation

**Best for**: Complete data collection, research projects

---

### Option B: Best ROI (3-4 hours total)
1. Phase 1 only: Fix parseable HTML teams
2. Document JS-rendered teams as "requires browser automation"
3. Skip Phase 2 and 3

**Best for**: Production use where 90% coverage is sufficient

---

### Option C: SEC Focus (8-10 hours)
1. Phase 2 for SEC schools only (12 teams)
2. Skip WCC and other JS-rendered schools
3. Fix infrastructure issues as encountered

**Best for**: SEC-specific research or recruiting

---

## Maintenance Considerations

### After Phase 1 (Parseable HTML)
- **Effort**: Low - standard HTML parsing
- **Breakage risk**: Medium - sites can change layout
- **Monitoring**: Run quarterly, check for parse failures

### After Phase 2 (Browser Automation)
- **Effort**: High - browser drivers need updates
- **Breakage risk**: High - JavaScript sites change frequently
- **Monitoring**: Run weekly, maintain browser compatibility
- **Cost**: Additional runtime (~2-5min per team vs. ~1-2sec)

### Best Practices
1. Run `python validation/validate_data.py` after each full scrape
2. Monitor `exports/scraper.log` for new "No players parsed" warnings
3. Update parsers incrementally as sites evolve in `scraper/roster.py`
4. Keep `settings/teams_urls.py` URLs updated (base URLs without year)
5. Consider setting up scheduled scraping (cron job)

---

## Alternative Solutions

### API-Based Approach
Some schools may have undocumented APIs. Check browser network tab for:
- `/api/roster` endpoints
- JSON responses in XHR requests
- GraphQL queries

**Pros**: Faster, more reliable than HTML parsing  
**Cons**: APIs may require authentication or be undocumented

### Manual Data Entry
For permanently unavailable schools, consider:
- PDF roster extraction
- Manual data entry from official sources
- Historical data from archive.org

---

## Success Metrics

| Phase | Coverage | Teams Added | Time Investment |
|-------|----------|-------------|-----------------|
| Current | 87.9% | - | 4 hours |
| Phase 1 | 90-91% | +7-10 | +3-4 hours |
| Phase 2 | 96-98% | +28 | +12-16 hours |
| Phase 3 | 98-100% | +4-7 | +1-2 hours |

---

## Getting Started

### To fix parseable HTML teams (Phase 1):
```bash
# 1. Analyze HTML structure
python -c "
from bs4 import BeautifulSoup
with open('fixtures/html/pacific.html') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
# Investigate structure...
"

# 2. Test new parser
python -m src.run_scraper --team "University of the Pacific"

# 3. Validate
grep "Pacific" exports/scraper.log
```

### To implement browser automation (Phase 2):
```bash
# 1. Install dependencies
pip install selenium
brew install chromedriver  # macOS

# 2. Create browser_scraper.py (see code above)

# 3. Test with one school
python -m src.run_scraper --team "University of Alabama" --use-browser

# 4. Roll out to all JS-rendered schools
```

---

## Questions?

See:
- `python validation/validate_data.py` - Data quality validation
- `settings/INCOMING_PLAYERS_README.md` - Incoming players data format
- `scripts/export_incoming_players.py --help` - Export incoming players to CSV
- `docs/TEST_README.md` - Testing guide
- `WARP.md` - Complete project documentation

Last Updated: 2025-11-29
