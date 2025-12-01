# utils.py
from __future__ import annotations

import re
from typing import Any, List, Set

import requests

from logging_utils import get_logger

logger = get_logger(__name__)


# ===================== GENERIC HELPERS =====================

def excel_unprotect(value: Any) -> str:
    """
    Convert protected Excel value ="6-2" -> 6-2.
    If not wrapped, return as string unchanged.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if s.startswith('="') and s.endswith('"'):
        return s[2:-1]
    return s


def normalize_text(value: Any) -> str:
    """
    Safely normalize arbitrary text.
    Returns a single stripped, single-spaced string.
    """
    if value is None:
        return ""

    if isinstance(value, (tuple, list)):
        try:
            value = " ".join(str(v) for v in value)
        except Exception:
            value = str(value)

    try:
        s = str(value)
    except Exception:
        s = ""

    return " ".join(s.split()).strip()


def fetch_html(url: str) -> str:
    logger.info("Fetching HTML: %s", url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; roster-stats-scraper/1.4)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def normalize_player_name(name: str) -> str:
    """
    Normalize roster player names:
      - Remove jersey numbers and stray digits.
      - Flip 'Last, First' -> 'First Last'.
    """
    s = normalize_text(name)

    # Strip trailing standalone digits
    s = re.sub(r"\b\d+\b", "", s)
    s = " ".join(s.split())

    # If "Last, First" format, flip
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2:
            s = f"{parts[1]} {parts[0]}"

    return s


def normalize_school_key(name: str) -> str:
    """
    Normalize school names so small differences still match.
    """
    s = normalize_text(name).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    stop_words = {"university", "college", "of", "the"}
    tokens = [t for t in s.split() if t and t not in stop_words]
    return " ".join(tokens)


def excel_protect_record(val: Any) -> str:
    """
    Protect dash-based records like '14-12' from Excel date conversion.
    """
    s = normalize_text(val)
    if not s:
        return ""
    if s.startswith('="'):
        return s
    if "-" in s and any(ch.isdigit() for ch in s):
        return f'="{s}"'
    return s


def excel_protect_phone(phone: Any) -> str:
    """
    Protect phone numbers from Excel auto-formatting.
    """
    s = normalize_text(phone)
    if not s:
        return ""
    return f'="{s}"'


# ===================== CLASS NORMALIZATION =====================

def normalize_class(raw: str) -> str:
    """
    Normalize the class string to one of:
      Fr, R-Fr, So, R-So, Jr, R-Jr, Sr, R-Sr, Gr, Fifth
    """
    if not raw:
        return ""

    s = normalize_text(raw).lower()
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Handle First Year (FY) variations
    if s in ("fy", "fy ", "first year", "first-year", "firstyear"):
        return "Fr"
    if s in ("rfr", "rfr ", "r-fy", "r fy", "rf", "rf ", "rfy", "r-fy ", "r-fr"):
        return "R-Fr"

    redshirt = False
    base = ""

    if "redshirt" in s or s.startswith("r "):
        redshirt = True

    if "fresh" in s or re.search(r"\bfr\b", s) or "first year" in s or re.search(r"\bfy\b", s):
        base = "Fr"
    elif "soph" in s or re.search(r"\bso\b", s):
        base = "So"
    elif "junior" in s or re.search(r"\bjr\b", s):
        base = "Jr"
    elif "senior" in s or re.search(r"\bsr\b", s):
        base = "Sr"
    elif "fifth" in s or "5th" in s or "6th" in s or "sixth" in s:
        base = "Fifth"
    elif "grad" in s or re.search(r"\bgr\b", s):
        base = "Gr"

    if base in {"Gr", "Fifth"}:
        return base

    if not base:
        return ""

    if redshirt and base in {"Fr", "So", "Jr", "Sr"}:
        return f"R-{base}"

    return base


def class_next_year(norm_or_raw: str) -> str:
    """
    Given a normalized (or raw) class string, return next year's class.
    """
    c = normalize_class(norm_or_raw)
    mapping = {
        "Fr": "So",
        "R-Fr": "R-So",
        "So": "Jr",
        "R-So": "R-Jr",
        "Jr": "Sr",
        "R-Jr": "R-Sr",
        "Sr": "Gr",
        "R-Sr": "Gr",
        "Gr": "Gr",
        "Fifth": "Gr",
    }
    return mapping.get(c, "")


def is_graduating(class_str: str) -> bool:
    """
    Returns True if the player is graduating at the end of the season.
    """
    norm = normalize_class(class_str)
    return norm in {"Sr", "R-Sr", "Gr", "Fifth"}


# ===================== HEIGHT & POSITION =====================

def normalize_height(raw: str) -> str:
    """
    Normalize height into 'F-I' (e.g. '6-2').
    """
    s = normalize_text(raw)
    if not s:
        return ""

    s = s.replace("’", "'").replace("`", "'")
    s = s.replace("\"", "").replace("in", "")
    s = s.strip().lower()

    # 6'2
    m = re.match(r"(\d+)\s*'\s*(\d+)", s)
    if not m:
        # 6-2, 6 - 02
        m = re.match(r"(\d+)\s*[-]\s*(\d+)", s)

    if m:
        feet = int(m.group(1))
        inches = int(m.group(2))
        if 0 <= inches < 12 and 4 <= feet <= 7:
            return f"{feet}-{inches}"

    nums = re.findall(r"\d+", s)
    if len(nums) == 2:
        feet = int(nums[0])
        inches = int(nums[1])
        if 0 <= inches < 12 and 4 <= feet <= 7:
            return f"{feet}-{inches}"

    return ""


def extract_position_codes(position: str) -> Set[str]:
    """
    Map a raw roster position string into a set of normalized codes:
      S, RS, OH, MB, DS
    Returns empty set if position looks like staff/coach role.
    """
    p_raw = normalize_text(position)
    if not p_raw:
        return set()

    p = p_raw.lower().replace(".", " ").strip()
    
    # Filter out staff positions
    staff_keywords = [
        "coach", "assistant", "director", "consultant", "coordinator",
        "analyst", "trainer", "manager", "intern", "video", "strength",
        "operations", "development", "technical", "volunteer", "graduate assistant"
    ]
    if any(kw in p for kw in staff_keywords):
        return set()
    
    parts = re.split(r"[\/,;]+", p)
    tokens: List[str] = []
    for part in parts:
        tokens.extend(part.split())

    joined = " ".join(tokens)
    codes: Set[str] = set()

    # Setter
    if "setter" in joined or re.search(r"\bs\b", joined):
        codes.add("S")

    # Right side / Opposite / Rightside Hitter
    if (
        "opp" in joined 
        or "opposite" in joined 
        or "right side" in joined
        or "rightside" in joined
        or re.search(r"\brs\b", joined)
        or re.search(r"\brh\b", joined)
    ):
        codes.add("RS")

    # Middle blocker
    if "middle" in joined or re.search(r"\bmb\b", joined) or re.search(r"\bmh\b", joined):
        codes.add("MB")

    # Outside hitter / Left side / Pin
    if (
        "outside" in joined 
        or "pin" in joined 
        or "left side" in joined
        or "left" in joined
        or re.search(r"\boh\b", joined)
        or re.search(r"\bls\b", joined)
    ):
        codes.add("OH")

    # Defensive specialist / Libero
    if (
        "libero" in joined
        or "defensive specialist" in joined
        or re.search(r"\bds\b", joined)
        or any(t in {"l", "lib"} for t in tokens)
    ):
        codes.add("DS")
    
    # Handle special combined positions
    # "Utility" = OH/DS, "UU" = OH/DS
    if "utility" in joined or re.search(r"\butl\b", joined) or re.search(r"\buu\b", joined):
        codes.add("OH")
        codes.add("DS")
    
    # "Opposite/Setter" = S/RS
    if ("opposite" in joined or "opp" in joined) and "setter" in joined:
        codes.add("S")
        codes.add("RS")
    
    # "Opposite Hitter/Middle Blocker" = RS/MB (already handled by individual checks above)
    # But explicitly handle if we see both in the string
    if ("opposite" in joined or "opp" in joined) and "middle" in joined:
        codes.add("RS")
        codes.add("MB")

    return codes


def canonical_name(name: str) -> str:
    """
    Canonicalize names for joining stats:
      - strip punctuation
      - lowercase
      - sort unique tokens
    """
    if not name:
        return ""
    s = normalize_text(name).lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    tokens = [t for t in s.split() if t]
    if not tokens:
        return ""
    tokens = sorted(set(tokens))
    return " ".join(tokens)
