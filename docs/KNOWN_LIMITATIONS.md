# Known Limitations

## Current Coverage: 305 of 347 teams (87.9%)

## Teams Currently Unavailable (42 teams)

### JavaScript-Rendered Sites (28 teams)
**Reason**: Sites use client-side JavaScript rendering  
**Symptom**: 114-byte redirect to `/lander` page  
**Fix Required**: Browser automation (Selenium/Playwright)  
**Priority**: Low (requires significant engineering effort)

#### Southeastern Conference (12 teams)
All SEC schools use the same JavaScript-rendered platform:
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

#### West Coast Conference (7 teams)
- Gonzaga University
- University of Portland
- University of San Diego
- University of San Francisco
- Santa Clara University
- Seattle University
- Washington State University

#### Summit League (4 teams)
- University of Denver
- University of North Dakota
- University of South Dakota
- University of St. Thomas

#### Other Conferences (5 teams)
- Lafayette College (Patriot League)
- Long Island University (NEC)
- Lamar University (Southland)
- University of New Orleans (Southland)
- Furman University (Southern Conference)
- Mercer University (Southern Conference)

---

### Infrastructure/Domain Issues (7 teams)
**Reason**: Broken URLs, domain parking, or access restrictions  
**Priority**: Low-Medium (may be temporary or permanent)

1. **University of New Mexico** (Mountain West)
   - Issue: Domain parking page
   - URL: https://gonewmexico.com/sports/womens-volleyball/roster
   - Status: Domain may have expired or changed

2. **University of Wyoming** (Mountain West)
   - Issue: Empty page
   - URL: https://gowyoming.com/sports/womens-volleyball/roster
   - Status: Site may be down or relocated

3. **Utah State University** (Mountain West)
   - Issue: JavaScript redirect (small page)
   - URL: https://utahstateathletics.com/sports/womens-volleyball/roster
   - Status: May have alternate URL or require browser

4. **Central Connecticut State University** (NEC)
   - Issue: 404 error or bot protection
   - URL: https://ccsubluedevils.com/sports/womens-volleyball/roster
   - Status: Path may have changed

5. **Tennessee Technological University** (Ohio Valley)
   - Issue: 404 error or bot protection
   - URL: https://ttusports.com/sports/womens-volleyball/roster
   - Status: Domain or path may need updating

6. **Mississippi Valley State University** (SWAC)
   - Fixed: Now at https://mvsusports.com
   - Note: Keep monitoring in case of changes

7. **University of Idaho** (Big Sky)
   - Issue: SSL certificate errors
   - URL: https://govandals.com/sports/womens-volleyball/roster
   - Status: Certificate issue may be temporary

---

### Parseable But Not Yet Implemented (7 teams)
**Reason**: HTML is accessible but needs custom parser  
**Priority**: Medium (achievable with 3-4 hours work)

1. **University of the Pacific** (WCC)
   - HTML Size: 44KB
   - Platform: Custom/SIDEARM variant
   - Fixture: `fixtures/html/pacific.html`

2. **Oregon State University** (WCC)
   - HTML Size: 3KB
   - Platform: Minimal page, may need investigation
   - Fixture: `fixtures/html/oregon_state.html`

3. **James Madison University** (Sun Belt)
   - HTML Size: 113KB
   - Platform: SIDEARM variant
   - Fixture: `fixtures/html/jmu.html`

4. **The Citadel** (Southern)
   - HTML Size: 44KB
   - Platform: SIDEARM variant
   - Fixture: `fixtures/html/citadel.html`

5. **Utah Tech University** (WAC)
   - HTML Size: 44KB
   - Platform: SIDEARM variant
   - Fixture: `fixtures/html/utah_tech.html`

6. **Troy University** (Sun Belt)
   - HTML Size: 792KB
   - Platform: May use s-person-details like Marshall
   - Fixture: `fixtures/html/troy.html`

7. **Possibly others** - Need investigation

---

## Workarounds

### For JavaScript-Rendered Sites
1. **Manual data entry**: Extract from live site viewing
2. **Browser automation**: Implement Selenium (see `FUTURE_ENHANCEMENTS.md`)
3. **API inspection**: Check browser DevTools for undocumented APIs
4. **Wait for site updates**: Some schools may switch platforms

### For Domain Issues
1. **Search for new domains**: Athletic departments sometimes rebrand
2. **Check archive.org**: May have historical roster data
3. **Contact athletic department**: Request roster information
4. **PDF rosters**: Some schools publish PDF rosters as fallback

### For Parseable Teams
1. **Analyze HTML structure**: Use `fixtures/html/*.html` files
2. **Implement custom parser**: Add to `roster.py`
3. **Test incrementally**: Use `--team` flag for targeted testing
4. **Validate data quality**: Use `scripts/validate_exports.py`

---

## Data Quality Notes

Even for successfully scraped teams, be aware of:

1. **Missing coach contact info**: Many schools don't publish emails/phones
2. **Inconsistent position codes**: Some schools use non-standard abbreviations
3. **Class year variations**: "R-Fr", "RS Fr", "Redshirt Freshman" all mean the same
4. **Height formats**: Various formats (6-2, 6'2", 6′2″) are normalized
5. **Transfer data**: Manually curated, may have gaps
6. **Stats availability**: Some schools don't publish detailed statistics

---

## Monitoring & Maintenance

### Recommended Schedule
- **Weekly**: Check `exports/scraper.log` for new failures
- **Monthly**: Run `scripts/compare_export_to_teams.py` to track coverage
- **Quarterly**: Full validation with `scripts/validate_exports.py --full`
- **Annually**: Review URLs for domain changes

### Early Warning Signs
```bash
# Check for new parsing failures
grep "No players parsed" exports/scraper.log | wc -l

# Compare current vs. expected coverage
python scripts/compare_export_to_teams.py

# Look for HTTP errors
grep -E "(404|500|SSL)" exports/scraper.log
```

### When Sites Change
1. Capture new HTML: `python scripts/snapshot_html.py --team "School Name"`
2. Analyze structure: `python -c "from bs4 import BeautifulSoup; ..."`
3. Update parser or URL in `settings/teams.py`
4. Test: `python run_scraper.py --team "School Name"`
5. Validate: Check `exports/scraper.log`

---

## Contact

For questions about coverage or to report issues:
1. Check `FUTURE_ENHANCEMENTS.md` for roadmap
2. Review `WARP.md` for project documentation
3. Run `scripts/validate_exports.py --help` for tooling help

Last Updated: 2025-11-29  
Last Full Scrape: 2025-11-29  
Coverage: 305/347 (87.9%)
