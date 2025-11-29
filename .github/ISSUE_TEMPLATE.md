# Volleyball Scraper - Future Enhancement Issues

## Phase 1: Parseable HTML Teams (90% Coverage Goal)

### Issue #1: Fix University of the Pacific Parser
**Priority**: Medium  
**Effort**: 1-2 hours  
**Impact**: +15-20 players

**Description**:
University of the Pacific roster page has parseable HTML (44KB) but doesn't match any current parser patterns.

**Tasks**:
- [ ] Analyze `fixtures/html/pacific.html` structure
- [ ] Identify HTML pattern (likely SIDEARM variant)
- [ ] Implement parser in `roster.py`
- [ ] Test with `python run_scraper.py --team "University of the Pacific"`
- [ ] Verify data quality in export
- [ ] Update documentation

**Files to modify**:
- `roster.py` - Add new parser or extend existing
- Tests (if applicable)

---

### Issue #2: Fix Oregon State Parser
**Priority**: Medium  
**Effort**: 1-2 hours  
**Impact**: +15-20 players

**Description**:
Oregon State has minimal HTML (3KB). May need investigation to determine if data is available or if it requires different approach.

**Tasks**:
- [ ] Analyze `fixtures/html/oregon_state.html` 
- [ ] Check if roster data is present or requires alternate URL
- [ ] Implement parser or update URL in `settings/teams.py`
- [ ] Test and validate
- [ ] Document findings

---

### Issue #3: Fix James Madison University Parser
**Priority**: Medium  
**Effort**: 1-2 hours  
**Impact**: +15-20 players

**Description**:
JMU has substantial HTML (113KB) with SIDEARM variant layout.

**Tasks**:
- [ ] Analyze `fixtures/html/jmu.html` for SIDEARM patterns
- [ ] Identify specific SIDEARM layout variant
- [ ] Implement or extend parser in `roster.py`
- [ ] Test with `python run_scraper.py --team "James Madison University"`
- [ ] Verify data quality

---

### Issue #4: Fix Citadel, Utah Tech, and Troy (Batch)
**Priority**: Medium  
**Effort**: 2-3 hours  
**Impact**: +45-60 players

**Description**:
Three teams with similar SIDEARM layouts (44KB each) that likely share a common pattern.

**Tasks**:
- [ ] Analyze all three HTML files in `fixtures/html/`
- [ ] Identify common parser pattern
- [ ] Implement single parser to handle all three
- [ ] Test each team individually
- [ ] Verify all data exports correctly

**Teams**:
- The Citadel (`fixtures/html/citadel.html`)
- Utah Tech University (`fixtures/html/utah_tech.html`)
- Troy University (`fixtures/html/troy.html`)

---

## Phase 2: Browser Automation (98% Coverage Goal)

### Issue #5: Implement Selenium/Playwright Infrastructure
**Priority**: Low  
**Effort**: 4-6 hours  
**Impact**: Foundation for 28 teams

**Description**:
Set up browser automation infrastructure to handle JavaScript-rendered sites (SEC schools and others).

**Tasks**:
- [ ] Research Selenium vs Playwright (recommend Playwright for better performance)
- [ ] Install dependencies: `pip install playwright && playwright install chromium`
- [ ] Create `browser_scraper.py` module
- [ ] Implement `fetch_html_with_browser(url, timeout)` function
- [ ] Add detection for JS-rendered pages in `utils.py`
- [ ] Add fallback logic in `roster.py` to use browser when needed
- [ ] Test with one SEC school (e.g., Alabama)
- [ ] Document setup and usage

**Code skeleton**:
```python
# browser_scraper.py
from playwright.sync_api import sync_playwright

def fetch_html_with_browser(url, timeout=10):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until='networkidle', timeout=timeout*1000)
        html = page.content()
        browser.close()
        return html
```

---

### Issue #6: Fix SEC Schools (JavaScript-Rendered) - Batch
**Priority**: Low  
**Effort**: 6-8 hours (after Issue #5)  
**Impact**: +180-240 players (12 teams)

**Description**:
All 12 SEC schools use JavaScript rendering with redirect to `/lander` page.

**Tasks**:
- [ ] Requires Issue #5 to be completed first
- [ ] Update `settings/teams.py` to mark SEC schools for browser scraping
- [ ] Test browser scraper with all 12 teams
- [ ] Implement rate limiting (2-3 seconds between requests)
- [ ] Add retry logic for timeouts
- [ ] Cache rendered HTML to `fixtures/` for testing
- [ ] Validate all 12 teams parse correctly
- [ ] Update coverage metrics

**Teams** (12):
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

---

### Issue #7: Fix WCC and Other JS-Rendered Schools
**Priority**: Low  
**Effort**: 4-6 hours (after Issue #5)  
**Impact**: +240-320 players (16 teams)

**Description**:
WCC and other conference schools using same JavaScript rendering approach.

**Tasks**:
- [ ] Requires Issue #5 to be completed first
- [ ] Apply browser scraping to 16 teams (see list below)
- [ ] Test and validate each school
- [ ] Update documentation

**Teams** (16):
- WCC (7): Gonzaga, Portland, San Diego, San Francisco, Santa Clara, Seattle, Washington State
- Summit (4): Denver, North Dakota, South Dakota, St. Thomas
- Others (5): Lafayette, LIU, Lamar, New Orleans, Furman, Mercer

---

## Phase 3: Infrastructure Fixes

### Issue #8: Research Domain Changes for Failed Schools
**Priority**: Low  
**Effort**: 1-2 hours  
**Impact**: +0-7 teams (depends on findings)

**Description**:
Several schools have infrastructure issues (domain parking, 404s, etc.).

**Tasks**:
- [ ] Research new domains for Wyoming, New Mexico
- [ ] Contact athletic departments if needed
- [ ] Check archive.org for historical roster URLs
- [ ] Update URLs in `settings/teams.py` if found
- [ ] Document permanently unavailable teams in `KNOWN_LIMITATIONS.md`

**Teams to investigate**:
- University of New Mexico (domain parking)
- University of Wyoming (empty page)
- Utah State University (redirect)
- Central Connecticut State (404/bot protection)
- Tennessee Tech (404/bot protection)
- University of Idaho (SSL errors)

---

## Maintenance & Monitoring

### Issue #9: Set Up Automated Coverage Monitoring
**Priority**: Medium  
**Effort**: 2-3 hours  
**Impact**: Ongoing quality assurance

**Description**:
Create automated monitoring to detect when parsers break or coverage drops.

**Tasks**:
- [ ] Create `scripts/monitor_coverage.py` 
- [ ] Set up weekly cron job to run scraper
- [ ] Generate comparison reports (week-over-week)
- [ ] Email/alert on coverage drops >5%
- [ ] Log parser failures to separate file
- [ ] Create dashboard/summary output

---

### Issue #10: Implement Data Quality Alerts
**Priority**: Medium  
**Effort**: 2-3 hours  
**Impact**: Data integrity

**Description**:
Automated alerts for data quality issues (invalid emails, phone formats, missing required fields).

**Tasks**:
- [ ] Enhance `scripts/validate_exports.py` with alert thresholds
- [ ] Define acceptable error rates per validation type
- [ ] Generate alerts when thresholds exceeded
- [ ] Create weekly data quality summary report
- [ ] Document validation rules

---

## Quick Start for Contributors

### Setting Up Development Environment
```bash
# Clone repo
git clone <repo-url>
cd vb_scraper

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pandas requests beautifulsoup4

# Run tests
python test_settings.py

# Test specific team
python run_scraper.py --team "Team Name"
```

### Before Submitting PR
```bash
# Run all tests
python test_settings.py

# Validate data quality
python scripts/validate_exports.py

# Check coverage impact
python scripts/compare_export_to_teams.py

# Review log for errors
grep -E "(ERROR|WARNING)" exports/scraper.log
```

---

## Issue Labels

Suggested labels for tracking:
- `phase-1-parseable` - Parseable HTML teams (quick wins)
- `phase-2-browser` - Requires browser automation
- `phase-3-infrastructure` - Domain/URL issues
- `enhancement` - New feature
- `bug` - Parser broken/regression
- `documentation` - Docs only
- `good-first-issue` - Good for new contributors
- `high-impact` - Affects many teams
- `quick-win` - Can be done in <2 hours

---

## Current Status

**Last Updated**: 2025-11-29  
**Coverage**: 305/347 teams (87.9%)  
**Player Records**: 11,777

**Phase 1 Potential**: 312-315 teams (90-91%)  
**Phase 2 Potential**: 333-338 teams (96-97%)  
**Phase 3 Potential**: 335-340 teams (98-100%)
