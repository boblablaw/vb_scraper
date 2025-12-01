# coaches_cache.py
"""
Helper module for loading and managing cached coaching staff data.
"""

import json
import os
from typing import Dict, List, Optional

from .logging_utils import get_logger

logger = get_logger(__name__)

DEFAULT_CACHE_FILE = "settings/coaches_cache.json"


def load_coaches_cache(cache_file: str = DEFAULT_CACHE_FILE) -> Dict[str, List[Dict]]:
    """
    Load coaches cache from JSON file.
    
    Args:
        cache_file: Path to cache file (default: settings/coaches_cache.json)
        
    Returns:
        Dict mapping team name -> list of coach dicts
        
    Example:
        >>> cache = load_coaches_cache()
        >>> stanford_coaches = cache.get("Stanford University", [])
        >>> for coach in stanford_coaches:
        ...     print(f"{coach['name']} - {coach['title']}")
    """
    if not os.path.exists(cache_file):
        logger.warning(f"Coaches cache file not found: {cache_file}")
        logger.info("Run 'python scripts/fetch_coaches.py' to create cache")
        return {}
    
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        generated_at = data.get("generated_at", "unknown")
        teams_data = data.get("teams", {})
        
        logger.info(f"Loaded coaches cache: {len(teams_data)} teams (generated: {generated_at})")
        
        # Convert to simple dict: team_name -> coaches list
        cache = {}
        for team_name, team_data in teams_data.items():
            cache[team_name] = team_data.get("coaches", [])
        
        return cache
        
    except Exception as e:
        logger.error(f"Error loading coaches cache: {e}")
        return {}


def get_coaches_for_team(team_name: str, cache: Optional[Dict] = None) -> List[Dict]:
    """
    Get coaches for a specific team from cache.
    
    Args:
        team_name: Name of team (e.g., "Stanford University")
        cache: Optional pre-loaded cache dict. If None, will load from file.
        
    Returns:
        List of coach dicts: [{"name": ..., "title": ..., "email": ..., "phone": ...}]
    """
    if cache is None:
        cache = load_coaches_cache()
    
    return cache.get(team_name, [])


def pack_coaches_for_row(coaches: List[Dict], max_coaches: int = 5) -> Dict[str, str]:
    """
    Pack coaches data into flat dict for CSV row.
    
    Args:
        coaches: List of coach dicts
        max_coaches: Maximum number of coaches to include (default: 5)
        
    Returns:
        Dict with keys: coach1_name, coach1_title, coach1_email, coach1_phone, etc.
    """
    result = {}
    
    for i in range(max_coaches):
        prefix = f"coach{i+1}"
        
        if i < len(coaches):
            coach = coaches[i]
            result[f"{prefix}_name"] = coach.get("name", "")
            result[f"{prefix}_title"] = coach.get("title", "")
            result[f"{prefix}_email"] = coach.get("email", "")
            result[f"{prefix}_phone"] = coach.get("phone", "")
        else:
            # Empty columns for missing coaches
            result[f"{prefix}_name"] = ""
            result[f"{prefix}_title"] = ""
            result[f"{prefix}_email"] = ""
            result[f"{prefix}_phone"] = ""
    
    return result
