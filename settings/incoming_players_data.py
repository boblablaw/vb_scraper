# incoming_players_data.py
"""
Automatic year-based incoming players data selector.

Date-based rules for selecting incoming players data:
- Aug 1, 2024 - Jul 31, 2025: Use 2025 data (incoming_players_data_2025.py)
- Aug 1, 2025 - Jul 31, 2026: Use 2026 data (incoming_players_data_2026.py)
- Aug 1, 2026 - Jul 31, 2027: Use 2027 data (incoming_players_data_2027.py)
- And so on...

The system automatically selects the correct dataset based on the current date.
"""

from datetime import datetime


def get_incoming_players_year():
    """
    Determine which year's incoming players data to use based on current date.
    
    Date ranges:
    - Aug 1 (year X) - Jul 31 (year X+1): Use year X+1 data
    
    Returns:
        int: The year of incoming players data to use (e.g., 2025, 2026)
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # If we're in Aug-Dec, use next year's data
    # If we're in Jan-Jul, use current year's data
    if current_month >= 8:
        return current_year + 1
    else:
        return current_year


def get_raw_incoming_text():
    """
    Get the appropriate RAW_INCOMING_TEXT based on current date.
    
    Returns:
        str: Raw incoming players text for the appropriate year
    """
    year = get_incoming_players_year()
    
    try:
        # Dynamically import the correct year's data
        import importlib
        module_name = f'incoming_players_data_{year}'
        module = importlib.import_module(f'.{module_name}', package='settings')
        raw_text = getattr(module, f'RAW_INCOMING_TEXT_{year}')
        return raw_text
    except (ImportError, AttributeError) as e:
        # Fall back to 2025 if the year's file doesn't exist
        print(f"Warning: Could not load incoming players data for {year}, falling back to 2025")
        print(f"Error: {e}")
        from .incoming_players_data_2025 import RAW_INCOMING_TEXT_2025
        return RAW_INCOMING_TEXT_2025


# For backward compatibility, expose RAW_INCOMING_TEXT
RAW_INCOMING_TEXT = get_raw_incoming_text()


if __name__ == "__main__":
    # Test the selector
    year = get_incoming_players_year()
    print(f"Current date: {datetime.now().strftime('%B %d, %Y')}")
    print(f"Using incoming players data for: {year}")
    print(f"Data length: {len(RAW_INCOMING_TEXT)} characters")
