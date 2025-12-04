# coaches.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from .utils import normalize_text, fetch_html
from .logging_utils import get_logger

logger = get_logger(__name__)

ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
}


def _ordinal_to_int(token: str) -> int | None:
    """
    Convert tokens like 'third', '3rd', '3' into an int.
    Returns None if it cannot be parsed or is unreasonable (>50).
    """
    if not token:
        return None

    t = token.strip().lower()
    t = re.sub(r"(st|nd|rd|th)$", "", t)

    if t.isdigit():
        val = int(t)
        if 0 < val < 50:
            return val
        return None

    return ORDINAL_WORDS.get(t)


def extract_tenure_from_text(text: str, current_year: int | None = None) -> tuple[int | None, int | None]:
    """
    Best-effort extraction of start year and seasons-at-school from a bio paragraph.

    Returns (start_year, seasons_at_school) where either may be None if not found.
    """
    if not text:
        return (None, None)

    current_year = current_year or datetime.now().year
    body = normalize_text(text)

    # Pattern: "enters her third season", "is in his 6th year", etc.
    season_match = re.search(
        r"(?:enter(?:ing|s)?|heading into|in|returns for|embarks on)\s+"
        r"(?:his|her|their)?\s*"
        r"(?P<num>\d{1,2}|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth)"
        r"(?:st|nd|rd|th)?\s+"
        r"(?:season|year)",
        body,
        flags=re.I,
    )

    seasons_at_school: int | None = None
    start_year: int | None = None

    if season_match:
        seasons_at_school = _ordinal_to_int(season_match.group("num"))
        if seasons_at_school and current_year:
            start_year = current_year - seasons_at_school + 1

    # Pattern: "hired in 2019", "since 2021", "joined ... in 2020"
    if start_year is None:
        year_match = re.search(
            r"(?:since|hired|joined|named|promoted|appointed|took over)\s+(?:in\s+)?(20\d{2})",
            body,
            flags=re.I,
        )
        if year_match:
            start_year = int(year_match.group(1))
            if current_year and start_year <= current_year:
                seasons_at_school = max(1, current_year - start_year + 1)

    return (start_year, seasons_at_school)


def find_coaches_page_url(roster_html: str, roster_url: str) -> str | None:
    """
    Try to find a dedicated 'Coaching Staff' or 'Coaches' page from the roster HTML.
    If not found via links, try common URL patterns.
    """
    soup = BeautifulSoup(roster_html, "html.parser")
    
    # Try "Coaching Staff" link first (but skip if it's just an anchor on same page)
    a = soup.find("a", string=lambda t: t and "Coaching Staff" in t)
    if a and a.get("href"):
        href = a["href"]
        if not href.startswith("#"):  # Skip in-page anchors
            url = urljoin(roster_url, href)
            logger.debug("Found Coaching Staff link: %s", url)
            return url

    # Try "Go To Coaching Staff"
    a = soup.find("a", string=lambda t: t and "Go To Coaching Staff" in t)
    if a and a.get("href"):
        href = a["href"]
        if not href.startswith("#"):
            url = urljoin(roster_url, href)
            logger.debug("Found 'Go To Coaching Staff' link: %s", url)
            return url
    
    # Try just "Coaches" link
    a = soup.find("a", string=lambda t: t and t.strip() == "Coaches")
    if a and a.get("href"):
        href = a["href"]
        if not href.startswith("#"):
            url = urljoin(roster_url, href)
            logger.debug("Found 'Coaches' link: %s", url)
            return url

    # If no link found, try common URL patterns
    # roster URL is typically like: https://site.com/sports/womens-volleyball/roster
    # coaches URL is typically: https://site.com/sports/womens-volleyball/coaches
    logger.debug("No dedicated coaching staff link found, trying common patterns...")
    
    if "/roster" in roster_url:
        # Try replacing /roster with /coaches
        coaches_url = roster_url.replace("/roster", "/coaches")
        logger.debug("Trying pattern URL: %s", coaches_url)
        return coaches_url
    elif roster_url.endswith("/"):
        coaches_url = roster_url + "coaches"
        logger.debug("Trying pattern URL: %s", coaches_url)
        return coaches_url
    
    logger.debug("Could not determine coaches page URL.")
    return None


def _find_bio_href(block) -> str | None:
    """
    Locate the first likely bio/profile link inside a coach block.
    """
    for a in block.find_all("a", href=True):
        href = a["href"]
        text = normalize_text(a.get_text())
        href_low = href.lower()
        text_low = text.lower()
        if "bio" in text_low or "profile" in text_low:
            return href
        if "/coach" in href_low or "/coaches" in href_low or "/staff/" in href_low:
            return href
    return None


def _enrich_with_bio(coach: dict, bio_href: str | None, base_url: str | None, fetch_bios: bool):
    """
    Optionally fetch a coach bio page and attach tenure info.
    """
    if not fetch_bios or not bio_href:
        return

    bio_url = urljoin(base_url, bio_href) if base_url else bio_href
    if not bio_url:
        return

    try:
        bio_html = fetch_html(bio_url)
    except Exception as e:
        logger.debug("Could not fetch bio %s: %s", bio_url, e)
        return

    try:
        bio_soup = BeautifulSoup(bio_html, "html.parser")
        bio_text = normalize_text(bio_soup.get_text(" ", strip=True))
        start_year, seasons_at_school = extract_tenure_from_text(bio_text)
        if start_year:
            coach["start_year"] = start_year
        if seasons_at_school:
            coach["seasons_at_school"] = seasons_at_school
        coach["bio_url"] = bio_url
    except Exception as e:
        logger.debug("Error parsing bio %s: %s", bio_url, e)


def parse_coaches_from_html(html: str, base_url: str | None = None, fetch_bios: bool = False) -> list[dict]:
    """
    Best-effort coach scraper.

    Returns a list of dicts: {"name", "title", "email", "phone", "start_year?", "seasons_at_school?", "bio_url?"}
    Tenure fields are filled only if `fetch_bios` is True and a coach bio link can be fetched.
    """
    soup = BeautifulSoup(html, "html.parser")
    coaches: list[dict] = []

    email_pattern = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        flags=re.I,
    )
    phone_pattern = re.compile(
        r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}",
        flags=re.I,
    )

    # ---------- 1) Sidearm-style coach containers ----------
    coach_blocks = soup.select(
        ".sidearm-roster-coach, "
        ".sidearm-roster-coaches li, "
        "li.sidearm-roster-coach, "
        "div.sidearm-coach, "
        "div.coach-card"
    )

    if coach_blocks:
        logger.debug("Found %d coach blocks (Sidearm-style).", len(coach_blocks))

        for block in coach_blocks:
            name = ""
            title = ""
            email = ""
            phone = ""

            name_tag = (
                block.find(class_="sidearm-roster-coach-name")
                or block.find("h3")
                or block.find("h2")
            )
            if name_tag:
                name = normalize_text(name_tag.get_text())

            title_tag = (
                block.find(class_="sidearm-roster-coach-title")
                or block.find("h4")
            )
            if title_tag:
                title = normalize_text(title_tag.get_text())

            block_text = normalize_text(block.get_text(" ", strip=True))

            for a in block.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:") and not email:
                    email = normalize_text(href.replace("mailto:", ""))
                elif href.startswith("tel:") and not phone:
                    phone = normalize_text(href.replace("tel:", ""))

            if not email:
                m_email = email_pattern.search(block_text)
                if m_email:
                    email = m_email.group(0)

            if not phone:
                m_phone = phone_pattern.search(block_text)
                if m_phone:
                    phone = m_phone.group(0)

            bio_href = _find_bio_href(block)

            if name:
                coach = {
                    "name": name,
                    "title": title,
                    "email": email,
                    "phone": phone,
                }
                _enrich_with_bio(coach, bio_href, base_url, fetch_bios)
                coaches.append(coach)

        if coaches:
            logger.info("Parsed %d coaches from Sidearm-style blocks.", len(coaches))
            return coaches

    # ---------- 2) Table-based coaching staff (e.g., UTSA) ----------
    # Look for "Coaching Staff" heading followed by a table
    for heading in soup.find_all(["h2", "h3", "h4", "h5"]):
        heading_text = normalize_text(heading.get_text()).lower()
        if "coaching staff" in heading_text or heading_text == "coaches":
            # Find table after this heading
            table = heading.find_next("table")
            if table:
                logger.debug("Found coaching staff table after heading: %s", heading_text)
                rows = table.find_all("tr")
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        # First cell is usually name, second is title
                        name_cell = cells[0]
                        title_cell = cells[1]
                        
                        name = normalize_text(name_cell.get_text())
                        title = normalize_text(title_cell.get_text())
                        
                        # Skip if name looks like header text
                        if name.lower() in {"name", "staff", "title"}:
                            continue
                        
                        # Look for email in remaining cells or row
                        email = ""
                        phone = ""
                        for cell in cells[2:]:
                            cell_text = normalize_text(cell.get_text())
                            if "@" in cell_text:
                                m_email = email_pattern.search(cell_text)
                                if m_email:
                                    email = m_email.group(0)
                            m_phone = phone_pattern.search(cell_text)
                            if m_phone:
                                phone = m_phone.group(0)
                        
                        # Also check for mailto/tel links in any cell
                        if not email:
                            email_tag = row.find("a", href=lambda h: h and h.startswith("mailto:"))
                            if email_tag:
                                email = email_tag["href"].replace("mailto:", "").strip()
                        if not phone:
                            phone_tag = row.find("a", href=lambda h: h and h.startswith("tel:"))
                            if phone_tag:
                                phone = phone_tag["href"].replace("tel:", "").strip()
                        
                        if name and title:
                            coaches.append({
                                "name": name,
                                "title": title,
                                "email": email,
                                "phone": phone,
                            })
                
                if coaches:
                    logger.info("Parsed %d coaches from coaching staff table.", len(coaches))
                    return coaches

    # ---------- 3) Fallback: staff-row style detection ----------

    coaches = []
    seen_names: set[str] = set()

    for a in soup.find_all("a", href=True):
        # Skip mailto: and tel: links - they're not names
        href = a.get("href", "")
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        
        name = normalize_text(a.get_text())
        if not name:
            continue

        lower_name = name.lower()

        # Skip common navigation/accessibility links
        if lower_name in {"image", "name", "title", "email", "phone number"}:
            continue
        if lower_name.startswith("full bio"):
            continue
        if lower_name.startswith("skip to"):
            continue
        if "jersey number" in lower_name:
            continue

        if "head coach" in lower_name or "assistant coach" in lower_name:
            continue

        parent = a.find_parent(["tr", "li", "div", "p"])
        if not parent:
            continue

        row_text = normalize_text(parent.get_text(" ", strip=True))
        row_lower = row_text.lower()

        staff_keywords = [
            "coach",
            "coordinator",
            "operations",
            "trainer",
            "strength & conditioning",
            "support staff",
            "director of volleyball",
        ]
        if not any(kw in row_lower for kw in staff_keywords):
            continue

        email = ""
        email_tag = parent.find("a", href=lambda h: h and h.startswith("mailto:"))
        if email_tag and email_tag.get("href"):
            email = email_tag["href"].split("mailto:")[-1].strip()
        else:
            m_email = email_pattern.search(row_text)
            if m_email:
                email = m_email.group(0)

        if not email:
            continue

        phone = ""
        phone_tag = parent.find("a", href=lambda h: h and "tel:" in h)
        if phone_tag and phone_tag.get("href"):
            phone = phone_tag["href"].split("tel:")[-1].strip()
        else:
            m_phone = phone_pattern.search(row_text)
            if m_phone:
                phone = m_phone.group(0)

        m_email_in_row = email_pattern.search(row_text)
        if m_email_in_row:
            before_email = row_text[: m_email_in_row.start()].strip()
        else:
            before_email = row_text

        if before_email.lower().startswith(name.lower()):
            title_part = before_email[len(name):].strip()
        else:
            title_part = before_email

        title_part = phone_pattern.sub("", title_part)
        title_part = email_pattern.sub("", title_part)
        title_part = (
            title_part
            .replace("/Volleyball", "")
            .replace("/volleyball", "")
        )
        title_part = re.sub(r"\s+", " ", title_part).strip(" ,;-")

        if not title_part:
            m_title = re.search(r"[^,;]*coach[^,;]*", row_text, flags=re.I)
            if m_title:
                title_part = m_title.group(0)
                title_part = phone_pattern.sub("", title_part)
                title_part = email_pattern.sub("", title_part)
                title_part = re.sub(r"\s+", " ", title_part).strip(" ,;-")

        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        coaches.append(
            {
                "name": name,
                "title": title_part,
                "email": email,
                "phone": phone,
            }
        )

    logger.info("Parsed %d coaches via fallback staff-row detection.", len(coaches))
    return coaches


def pack_coaches_for_row(coaches: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Flatten up to 5 coaches into:
      coach1_name, coach1_title, coach1_email, coach1_phone, ...
    """
    out: Dict[str, str] = {}
    max_coaches = 5

    for idx in range(1, max_coaches + 1):
        out[f"coach{idx}_name"] = ""
        out[f"coach{idx}_title"] = ""
        out[f"coach{idx}_email"] = ""
        out[f"coach{idx}_phone"] = ""
        out[f"coach{idx}_start_year"] = ""
        out[f"coach{idx}_seasons_at_school"] = ""

    if not coaches:
        return out

    for idx, c in enumerate(coaches[:max_coaches], start=1):
        out[f"coach{idx}_name"] = normalize_text(c.get("name", ""))
        out[f"coach{idx}_title"] = normalize_text(c.get("title", ""))
        out[f"coach{idx}_email"] = normalize_text(c.get("email", ""))
        out[f"coach{idx}_phone"] = normalize_text(c.get("phone", ""))
        out[f"coach{idx}_start_year"] = c.get("start_year", "") or ""
        out[f"coach{idx}_seasons_at_school"] = c.get("seasons_at_school", "") or ""

    return out
