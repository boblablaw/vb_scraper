# teams_urls.py
"""
Automatic year-based URL management for team rosters and stats.

Date-based rules for URL years:
- Aug 1, 2024 - Jul 31, 2025: Use /2024 in URLs (2024 season data)
- Aug 1, 2025 - Jul 31, 2026: Use /2025 in URLs (2025 season data)
- Aug 1, 2026 - Jul 31, 2027: Use /2026 in URLs (2026 season data)
- And so on...

The system automatically appends the correct year to roster and stats URLs.
"""

from datetime import datetime
from settings.teams import TEAMS


def get_season_year():
    """
    Determine which season year to use for URLs based on current date.
    
    Date ranges:
    - Aug 1 (year X) - Jul 31 (year X+1): Use year X for URLs
    
    Returns:
        int: The season year to use in URLs (e.g., 2024, 2025)
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # If we're in Aug-Dec, use current year (new season starting)
    # If we're in Jan-Jul, use previous year (season in progress)
    if current_month >= 8:
        return current_year
    else:
        return current_year - 1


def append_year_to_url(url, year):
    """
    Append year to URL if not already present.
    
    Args:
        url: Base URL (e.g., "https://site.com/roster")
        year: Year to append (e.g., 2025)
        
    Returns:
        str: URL with year (e.g., "https://site.com/roster/2025")
    """
    if not url:
        return url
    
    # Check if year is already in URL
    year_str = str(year)
    if f"/{year_str}" in url or f"={year_str}" in url:
        return url
    
    # Remove trailing slash if present
    url = url.rstrip('/')
    
    # Append year
    return f"{url}/{year_str}"


def get_teams_with_year_urls(year=None):
    """
    Get teams list with year-specific URLs.
    
    Args:
        year: Optional year to use. If None, auto-selects based on date.
        
    Returns:
        list: Teams list with URLs containing the year
    """
    if year is None:
        year = get_season_year()
    
    teams_with_year = []
    
    for team in TEAMS:
        team_copy = team.copy()
        
        # Append year to URLs
        if 'url' in team_copy:
            team_copy['url'] = append_year_to_url(team_copy['url'], year)
        
        if 'stats_url' in team_copy:
            team_copy['stats_url'] = append_year_to_url(team_copy['stats_url'], year)
        
        teams_with_year.append(team_copy)
    
    return teams_with_year


# For backward compatibility, expose TEAMS_WITH_YEAR
TEAMS_WITH_YEAR = get_teams_with_year_urls()


if __name__ == "__main__":
    # Test the selector
    year = get_season_year()
    print(f"Current date: {datetime.now().strftime('%B %d, %Y')}")
    print(f"Using season year for URLs: {year}")
    print()
    
    # Show a few examples
    teams = get_teams_with_year_urls()
    print("Sample teams with year-appended URLs:")
    for team in teams[:3]:
        print(f"\n{team['team']}:")
        print(f"  Roster: {team['url']}")
        print(f"  Stats:  {team['stats_url']}")
