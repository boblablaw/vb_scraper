# roster.py
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from utils import normalize_text
from logging_utils import get_logger

logger = get_logger(__name__)

# ===================== GENERIC CONSTANTS =====================

# Height patterns like: 6-2, 5-11, 6'2, 6′2″, etc.
HEIGHT_RE = re.compile(
    r"""
    ^\s*
    (?:
        \d{1,2}[--]\d{1,2}      # 6-2, 5-11
        |
        \d{1,2}'\d{1,2}"?       # 6'2 or 6'2"
        |
        \d{1,2}[′’]\d{1,2}[″"]? # 6′2 or 6′2″
    )
    \s*$
    """,
    re.VERBOSE,
)


def _clean(text: str | None) -> str:
    return normalize_text(text or "")


def _is_staff_block(tag: Tag) -> bool:
    """
    Heuristic: is this part of a coaching/support staff section?
    """
    txt = normalize_text(tag.get_text(" ", strip=True))
    low = txt.lower()
    if any(kw in low for kw in ("coaching staff", "support staff", "staff directory")):
        return True
    # Also consider headings that look like "Head Coach" etc.
    if tag.name in ("h1", "h2", "h3", "h4"):
        if "coach" in low or "staff" in low:
            return True
    return False


# ===================== SIDEARM CARD LAYOUT =====================


def parse_sidearm_card_layout(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Parse classic SIDEARM / NextGen card-based rosters.

    Looks for roster cards / player tiles with player name, position, height, class.
    Returns list of dicts with keys: name, position, class_raw, height_raw.
    """
    players: List[Dict[str, str]] = []

    card_selectors = [
        ".sidearm-roster-player",
        ".sidearm-roster-card",
        "li.sidearm-roster-player",
        "li.sidearm-roster-card",
    ]
    cards = soup.select(",".join(card_selectors))
    
    # Deduplicate cards in case some selectors overlap
    # (e.g., .sidearm-roster-player and li.sidearm-roster-player)
    seen_cards = set()
    unique_cards = []
    for card in cards:
        card_id = id(card)
        if card_id not in seen_cards:
            seen_cards.add(card_id)
            unique_cards.append(card)
    cards = unique_cards
    if not cards:
        return players

    for card in cards:
        # Skip coaching / staff cards by heading text
        text_sample = normalize_text(card.get_text(" ", strip=True))
        if "coach" in text_sample.lower() and "volleyball" not in text_sample.lower():
            # usually coaching staff blocks mention coach prominently
            continue

        # Name
        name_tag = (
            card.find(class_="sidearm-roster-player-name")
            or card.find(class_="sidearm-roster-player-name-link")
            or card.find("h3")
            or card.find("h2")
            or card.find("a", href=True)
        )
        name = _clean(name_tag.get_text()) if name_tag else ""

        # Position
        pos_tag = (
            card.find(class_="sidearm-roster-player-position")
            or card.find(class_="sidearm-roster-player-pos")
            or card.find("span", class_=re.compile("pos", re.I))
        )
        position = _clean(pos_tag.get_text()) if pos_tag else ""

        # Class / year
        class_tag = (
            card.find(class_="sidearm-roster-player-academic-year")
            or card.find(class_="sidearm-roster-player-year")
            or card.find("span", class_=re.compile("class|year", re.I))
        )
        class_raw = _clean(class_tag.get_text()) if class_tag else ""

        # Height
        height_tag = (
            card.find(class_="sidearm-roster-player-height")
            or card.find("span", class_=re.compile("height", re.I))
        )
        height_raw = _clean(height_tag.get_text()) if height_tag else ""

        if not name:
            continue

        players.append(
            {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
            }
        )

    if players:
        logger.info("Parsed %d players from SIDEARM-like cards.", len(players))

    return players


# ===================== SIDEARM TABLE LAYOUT =====================


def parse_sidearm_table(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Parse classic SIDEARM table rosters.

    Looks for a <table> whose header has name / pos / class and optionally height.
    Returns list of dicts: {name, position, class_raw, height_raw}.
    """
    players: List[Dict[str, str]] = []
    tables = soup.find_all("table")

    for table in tables:
        thead = table.find("thead")
        if not thead:
            continue

        header_cells = thead.find_all("th")
        headers = [normalize_text(th.get_text()) for th in header_cells]
        header_lower = [h.lower() for h in headers]

        def find_col(keyword_list: List[str]) -> Optional[int]:
            for kw in keyword_list:
                for idx, h in enumerate(header_lower):
                    if kw in h:
                        return idx
            return None

        name_idx = find_col(["name", "player"])
        pos_idx = find_col(["pos", "position"])
        class_idx = find_col(["class", "year", "yr", "eligibility", "cl"])
        height_idx = find_col(["ht", "height"])

        if name_idx is None or pos_idx is None:
            continue

        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            texts = [normalize_text(c.get_text()) for c in cells]

            def get(idx: Optional[int]) -> str:
                if idx is None:
                    return ""
                if 0 <= idx < len(texts):
                    return texts[idx]
                return ""

            name = get(name_idx)
            position = get(pos_idx)
            class_raw = get(class_idx)
            height_raw = get(height_idx)

            # Staff filter: skip obvious staff/coaches rows
            lower_row = " ".join(texts).lower()
            lower_pos = position.lower()
            
            # Skip if contains coach (but not if it's about volleyball coaching)
            if "coach" in lower_row and "volleyball" not in lower_row:
                continue
            
            # Skip if position contains staff keywords
            staff_keywords = ['director', 'coordinator', 'trainer', 'advisor', 'communications', 
                            'operations', 'strength', 'conditioning', 'manager', 'admin']
            if any(kw in lower_pos for kw in staff_keywords):
                continue

            if not name:
                continue

            players.append(
                {
                    "name": name,
                    "position": position,
                    "class_raw": class_raw,
                    "height_raw": height_raw,
                }
            )

    if players:
        logger.info("Parsed %d players from SIDEARM-like table.", len(players))

    return players


# ===================== DRUPAL VIEWS ROSTER TABLE =====================


def parse_drupal_views_roster(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Handles Drupal Views roster tables such as older BYU / similar sites.

    Example row:
       <td class="views-field-title"> Anna Blamires </td>
       <td class="views-field-field-position"> Outside Hitter </td>
       <td class="views-field-field-height"> 6-2 </td>
       <td class="views-field-field-year"> Freshman </td>
       <td class="views-field-field-hometown"> Euless, Texas </td>
    """
    players: List[Dict[str, str]] = []

    rows = soup.select("table tr")
    if not rows:
        return players

    for row in rows:
        # Skip header rows
        if row.find("th"):
            continue

        name_td = row.select_one(".views-field-title, .views-field-name")
        pos_td = row.select_one(".views-field-field-position")
        height_td = row.select_one(".views-field-field-height")
        year_td = row.select_one(".views-field-field-year, .views-field-field-class")
        hometown_td = row.select_one(".views-field-field-hometown")

        if not name_td:
            continue

        name = _clean(name_td.get_text())
        position = _clean(pos_td.get_text()) if pos_td else ""
        height_raw = _clean(height_td.get_text()) if height_td else ""
        class_raw = _clean(year_td.get_text()) if year_td else ""
        # hometown not used but could be: hometown = _clean(hometown_td.get_text()) if hometown_td else ""

        if not name:
            continue

        players.append(
            {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
            }
        )

    if players:
        logger.info("Parsed %d players from Drupal Views roster.", len(players))

    return players


# ===================== HEADING / CARD (WMT) ROSTER =====================


def parse_heading_card_roster(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Handles WMT-style or generic heading+detail layouts where each player has:

        <h3><a>Player Name</a></h3>
        <div>Position · Height · Class · Hometown</div>

    This is a best-effort parser for sites like some WMT deployments.
    """
    players: List[Dict[str, str]] = []

    name_links = soup.select(
        "h1 a[href*='/roster/'], "
        "h2 a[href*='/roster/'], "
        "h3 a[href*='/roster/'], "
        "h4 a[href*='/roster/']"
    )
    if not name_links:
        return players

    for a in name_links:
        heading = a.find_parent(["h1", "h2", "h3", "h4"])
        if not heading:
            continue

        # Skip if this heading is clearly within a staff section
        ancestor = heading
        skip = False
        while ancestor:
            if _is_staff_block(ancestor):
                skip = True
                break
            ancestor = ancestor.parent if isinstance(ancestor.parent, Tag) else None
        if skip:
            continue

        name = _clean(a.get_text())
        if not name:
            continue

        # Look for the next sibling that has some details text
        details_text = ""
        sib = heading.find_next_sibling()
        while sib and isinstance(sib, Tag):
            details_text = normalize_text(sib.get_text(" ", strip=True))
            if details_text:
                break
            sib = sib.find_next_sibling()

        position = ""
        height_raw = ""
        class_raw = ""

        if details_text:
            tokens = details_text.split()
            # Height is usually a token that matches HEIGHT_RE
            height_idx = None
            for idx, tok in enumerate(tokens):
                if HEIGHT_RE.match(tok):
                    height_idx = idx
                    break

            if height_idx is not None:
                position = " ".join(tokens[:height_idx]).strip()
                height_raw = tokens[height_idx].strip()

                # Everything after height may contain class/year; we try simple heuristics
                tail = " ".join(tokens[height_idx + 1 :])
                # grab first capitalized word like Freshman, Sophomore, Junior, Senior, etc.
                m = re.search(
                    r"(Freshman|Sophomore|Junior|Senior|Graduate|Redshirt(?:\s+\w+)?)",
                    tail,
                    re.IGNORECASE,
                )
                if m:
                    class_raw = m.group(0)

        players.append(
            {
                "name": name,
                "position": _clean(position),
                "class_raw": _clean(class_raw),
                "height_raw": _clean(height_raw),
            }
        )

    # Filter out empty ones
    players = [p for p in players if p["name"]]

    if players:
        logger.info("Parsed %d players from heading-card roster.", len(players))

    return players


# ===================== EMBEDDED JSON ROSTER =====================


def parse_roster_from_sidearm_json(html: str, url: str) -> List[Dict[str, str]]:
    """
    Some SIDEARM / NextGen implementations embed a JSON blob with roster data,
    often in a <script type="application/ld+json"> tag or custom JS variable.

    We do a very simple JSON sniff looking for arrays of objects with
    name / position / height / class-like fields.
    
    Also handles embedded JavaScript arrays with detailed player data
    (e.g., George Mason format with height_feet, position_short, academic_year_short).
    
    IMPORTANT: Filters out non-volleyball players if >30 players are found
    (likely multi-sport JSON data).
    """
    players: List[Dict[str, str]] = []
    
    # Valid volleyball position codes (case-insensitive)
    VALID_VB_POSITIONS = {'s', 'setter', 'oh', 'outside', 'outside hitter', 'rs', 'right side', 
                          'opposite', 'opp', 'mb', 'mh', 'middle', 'middle blocker', 'middle hitter',
                          'ds', 'defensive specialist', 'l', 'libero', 'def specialist'}
    
    def is_volleyball_position(pos: str) -> bool:
        """Check if position string contains a valid volleyball position code."""
        if not pos:
            return False
        pos_lower = pos.lower().strip()
        return any(vb_pos in pos_lower for vb_pos in VALID_VB_POSITIONS)
    
    # First, try to find embedded JavaScript array with detailed player objects
    # Look for arrays containing objects with fields like "height_feet", "position_short", "academic_year_short"
    pattern = r'\[\s*\{[^}]{0,500}"height_feet"[^}]{0,500}"position_short"'
    match = re.search(pattern, html)
    
    if match:
        logger.info("Found embedded JavaScript roster array at position %d", match.start())
        start_pos = match.start()
        
        # Count brackets to find the array end
        bracket_count = 0
        i = start_pos
        while i < len(html) and i < start_pos + 100000:  # Safety limit
            if html[i] == '[':
                bracket_count += 1
            elif html[i] == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    break
            i += 1
        
        if bracket_count == 0:
            end_pos = i + 1
            json_str = html[start_pos:end_pos]
            
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    logger.info("Parsed embedded roster array with %d items", len(data))
                    
                    for obj in data:
                        if not isinstance(obj, dict):
                            continue
                        
                        # Extract name
                        first_name = obj.get('first_name', '')
                        last_name = obj.get('last_name', '')
                        name = _clean(f"{first_name} {last_name}".strip())
                        
                        if not name:
                            continue
                        
                        # Extract position
                        position = _clean(obj.get('position_short', '') or obj.get('position_long', ''))
                        
                        # Extract height from height_feet and height_inches
                        height_feet = obj.get('height_feet')
                        height_inches = obj.get('height_inches')
                        height_raw = ""
                        if height_feet and height_inches is not None:
                            height_raw = f"{height_feet}-{height_inches}"
                        
                        # Extract class/year
                        class_raw = _clean(
                            obj.get('academic_year_short', '')
                            or obj.get('academic_year_long', '')
                            or obj.get('class', '')
                        )
                        
                        players.append({
                            "name": name,
                            "position": position,
                            "class_raw": class_raw,
                            "height_raw": height_raw,
                        })
                    
                    if players:
                        return players
                        
            except (json.JSONDecodeError, ValueError) as e:
                logger.debug("Could not parse embedded roster array as JSON: %s", e)

    # 1) application/ld+json blocks
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script"):
        if not script.string:
            continue
        text = script.string.strip()
        if not text:
            continue

        # Try pure JSON first
        data = None
        if text.startswith("{") or text.startswith("["):
            try:
                data = json.loads(text)
            except Exception:
                data = None
        # Very simple var = ... JSON pattern
        if data is None:
            m = re.search(r"=\s*({.*});?$", text, flags=re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                except Exception:
                    data = None

        if data is None:
            continue

        def extract_from_obj(obj: Dict[str, Any]) -> Optional[Dict[str, str]]:
            name = _clean(
                obj.get("name")
                or obj.get("full_name")
                or obj.get("athlete_name")
                or ""
            )
            if not name:
                return None

            position = _clean(
                obj.get("position")
                or obj.get("pos")
                or obj.get("primary_position")
                or ""
            )
            height_raw = _clean(
                obj.get("height")
                or obj.get("ht")
                or ""
            )
            class_raw = _clean(
                obj.get("class")
                or obj.get("academic_year")
                or obj.get("year")
                or ""
            )
            return {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
            }

        # Data could be a list, or a dict with a key containing list
        if isinstance(data, list):
            for obj in data:
                if isinstance(obj, dict):
                    rec = extract_from_obj(obj)
                    if rec:
                        players.append(rec)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for obj in value:
                        if isinstance(obj, dict):
                            rec = extract_from_obj(obj)
                            if rec:
                                players.append(rec)

    if players:
        # Filter out non-volleyball positions if we have >30 players
        # (likely grabbed all sports from a multi-sport JSON blob)
        if len(players) > 30:
            vb_players = [p for p in players if is_volleyball_position(p.get('position', ''))]
            if vb_players:
                logger.info(
                    "Filtered %d/%d players to volleyball positions only from JSON in %s.",
                    len(vb_players), len(players), url
                )
                return vb_players
            else:
                # No valid volleyball positions found - this is likely garbage data
                # Cap at 25 players as a safety measure
                logger.warning(
                    "Found %d players with no volleyball positions in JSON from %s. "
                    "Capping at 25 players to avoid garbage data.",
                    len(players), url
                )
                return players[:25]
        
        logger.info(
            "Parsed %d players from embedded JSON roster in %s.", len(players), url
        )

    return players


# ===================== NUMBER / NAME / DETAILS TEXT ROSTER (BYU) =====================


def parse_number_name_details_roster(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Generic text-based fallback for rosters encoded as:

        <jersey number>
        <player name>
        <details line>

    where the details line looks like:

        Outside Hitter 6-2 Freshman Euless, Texas Colleyville Heritage High School

    This pattern is used by BYU and other sites.

    We return dicts with: name, position, class_raw, height_raw.
    """
    YEAR_WORDS = {
        "fr",
        "fr.",
        "freshman",
        "so",
        "so.",
        "sophomore",
        "jr",
        "jr.",
        "junior",
        "sr",
        "sr.",
        "senior",
        "gr",
        "gr.",
        "graduate",
        "r-fr",
        "r-so",
        "r-jr",
        "r-sr",
        "redshirt",
    }

    def parse_details_line(details: str) -> Optional[Dict[str, str]]:
        tokens = details.split()
        if not tokens:
            return None

        # Find height token (supports 6-2, 6'2, 5′11, etc.)
        height_idx: Optional[int] = None
        for idx, tok in enumerate(tokens):
            if HEIGHT_RE.match(tok):
                height_idx = idx
                break

        if height_idx is None:
            return None

        position = " ".join(tokens[:height_idx]).strip()
        height = tokens[height_idx].strip()

        # Look for class/year token after height
        class_start: Optional[int] = None
        class_end: Optional[int] = None
        j = height_idx + 1
        while j < len(tokens):
            low = tokens[j].strip(",").lower()
            if low in YEAR_WORDS:
                class_start = j
                class_end = j
                k = j + 1
                while k < len(tokens):
                    low2 = tokens[k].strip(",").lower()
                    if low2 in YEAR_WORDS or low2 == "redshirt":
                        class_end = k
                        k += 1
                    else:
                        break
                break
            j += 1

        if class_start is None:
            return None

        class_raw = " ".join(tokens[class_start : class_end + 1]).strip()

        if not position or not height or not class_raw:
            return None

        return {
            "position": _clean(position),
            "height_raw": _clean(height),
            "class_raw": _clean(class_raw),
        }

    lines = [normalize_text(t) for t in soup.stripped_strings]
    players: List[Dict[str, str]] = []

    i = 0
    n = len(lines)
    while i < n - 2:
        jersey = lines[i].lstrip("#")
        # Jersey numbers: 1–2 digits, occasionally 0 or 3+ but rare
        if jersey.isdigit() and 1 <= len(jersey) <= 2:
            name = normalize_text(lines[i + 1]) if i + 1 < n else ""
            details = normalize_text(lines[i + 2]) if i + 2 < n else ""

            parsed = parse_details_line(details)
            if parsed and name:
                players.append(
                    {
                        "name": name,
                        "position": parsed["position"],
                        "class_raw": parsed["class_raw"],
                        "height_raw": parsed["height_raw"],
                    }
                )
                i += 3
                continue

        i += 1

    if players:
        logger.info(
            "Parsed %d players from number-name-details text roster.", len(players)
        )

    return players


# ===================== GENERIC TABLE FALLBACK =====================


def parse_generic_table_roster(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Very generic table parser used only as a last resort.

    Tries to infer which column is name, position, class, height.
    This can mis-parse some schools, so we only use it when all other
    strategies fail.
    """
    players: List[Dict[str, str]] = []

    for table in soup.find_all("table"):
        # require at least 2 rows
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [normalize_text(th.get_text()) for th in header_cells]
        header_lower = [h.lower() for h in headers]

        def col_index(candidates: List[str]) -> Optional[int]:
            for c in candidates:
                for idx, h in enumerate(header_lower):
                    if c in h:
                        return idx
            return None

        name_idx = col_index(["name", "player"])
        pos_idx = col_index(["pos", "position"])
        class_idx = col_index(["class", "year"])
        height_idx = col_index(["ht", "height"])

        if name_idx is None:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            texts = [normalize_text(c.get_text()) for c in cells]

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(texts):
                    return ""
                return texts[idx]

            name = get(name_idx)
            position = get(pos_idx)
            class_raw = get(class_idx)
            height_raw = get(height_idx)

            if not name:
                continue

            players.append(
                {
                    "name": name,
                    "position": position,
                    "class_raw": class_raw,
                    "height_raw": height_raw,
                }
            )

    if players:
        logger.info("Parsed %d players from generic roster table.", len(players))

    return players


# ===================== OPTIONAL WMT TEXT ENRICHMENT =====================


def enrich_wmt_roster_from_text(
    html: str, soup: BeautifulSoup, players: List[Dict[str, str]], url: str
) -> List[Dict[str, str]]:
    """
    If we only have names for a WMT roster, try to enrich from nearby text blocks.

    This is deliberately conservative: we only try to attach obvious
    "Position Height Class" sequences when they appear close to the player name.
    """
    # For now, this is a no-op that just returns players as-is.
    # The interface is kept so we can plug in smarter enrichment later
    # without changing callers.
    return players


# ===================== TOP-LEVEL DISPATCH =====================


def parse_roster(html: str, url: str) -> List[Dict[str, str]]:
    """
    Unifying roster parser.

    Strategy, in order:
      1) SIDEARM / NextGen card layout
      2) SIDEARM-style table layout   (with sanity check to avoid misaligned cases)
      3) Heading-card (WMT) layout
      4) Drupal Views roster tables
      5) Embedded JSON roster
      6) Number / name / details text roster (BYU and similar)
      7) Very generic roster tables
      8) Optional WMT text enrichment + height back-fill.

    Returns list of dicts:
      { "name", "position", "class_raw", "height_raw" }
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) SIDEARM / NextGen cards
    players = parse_sidearm_card_layout(soup)

    # 2) SIDEARM-like tables
    if not players:
        players = parse_sidearm_table(soup)

        # Sanity check: if "position" field looks like height for the majority
        # of players (e.g. BYU table view where columns are mis-identified),
        # discard and fall back to other strategies.
        if players:
            bad_pos = sum(
                1
                for p in players
                if HEIGHT_RE.search((p.get("position") or "").strip())
            )
            if bad_pos >= max(1, len(players) // 2):
                logger.info(
                    "SIDEARM-like table looked misaligned (%d/%d 'position' cells "
                    "look like heights); discarding and falling back.",
                    bad_pos,
                    len(players),
                )
                players = []

    # 3) Heading-card roster (WMT-style)
    if not players:
        players = parse_heading_card_roster(soup)

    # 4) Drupal Views roster tables
    if not players:
        players = parse_drupal_views_roster(soup)

    # 5) Embedded JSON blobs
    if not players:
        logger.info("Fallback: trying embedded JSON roster for %s ...", url)
        players = parse_roster_from_sidearm_json(html, url)

    # 6) Number / name / details text roster (BYU-style list/table view)
    if not players:
        logger.info(
            "No structured roster found for %s; trying number-name-details text fallback.",
            url,
        )
        players = parse_number_name_details_roster(soup)

    # 7) Very generic roster tables as absolute last resort
    if not players:
        players = parse_generic_table_roster(soup)

    if not players:
        logger.warning("No players parsed from roster %s.", url)
        return players

    # 8a) Optional: WMT-specific text enrichment if we only have names
    if all(
        not p.get("position") and not p.get("class_raw") and not p.get("height_raw")
        for p in players
    ):
        lower_html = html.lower()
        if "wmt digital" in lower_html or "powered by wmt" in lower_html:
            logger.info("Attempting WMT text-based roster enrichment for %s ...", url)
            players = enrich_wmt_roster_from_text(html, soup, players, url)

    # 8b) Back-fill heights if needed (only if all players missing height_raw)
    if all(not p.get("height_raw") for p in players):
        text = soup.get_text("\n", strip=True)
        height_matches = re.findall(r"Height\s+([^\n]+)", text)
        height_matches = [normalize_text(h) for h in height_matches]
        if len(height_matches) >= len(players):
            logger.info(
                "Back-filling heights from text for %s (found %d heights).",
                url,
                len(height_matches),
            )
            for p, h in zip(players, height_matches):
                p["height_raw"] = h

    return players