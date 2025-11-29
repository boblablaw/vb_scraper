# coaches.py
from __future__ import annotations

import re
from typing import Dict, List

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import normalize_text, excel_protect_phone
from logging_utils import get_logger

logger = get_logger(__name__)


def find_coaches_page_url(roster_html: str, roster_url: str) -> str | None:
    """
    Try to find a dedicated 'Coaching Staff' or 'Coaches' page from the roster HTML.
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

    logger.debug("No dedicated coaching staff link found on roster page.")
    return None


def parse_coaches_from_html(html: str) -> list[dict]:
    """
    Best-effort coach scraper.

    Returns a list of dicts: {"name", "title", "email", "phone"}.
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

            if name:
                coaches.append(
                    {
                        "name": name,
                        "title": title,
                        "email": email,
                        "phone": phone,
                    }
                )

        if coaches:
            logger.info("Parsed %d coaches from Sidearm-style blocks.", len(coaches))
            return coaches

    # ---------- 2) Fallback: staff-row style detection ----------

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

        if lower_name in {"image", "name", "title", "email", "phone number"}:
            continue
        if lower_name.startswith("full bio"):
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

    if not coaches:
        return out

    for idx, c in enumerate(coaches[:max_coaches], start=1):
        out[f"coach{idx}_name"] = normalize_text(c.get("name", ""))
        out[f"coach{idx}_title"] = normalize_text(c.get("title", ""))
        out[f"coach{idx}_email"] = normalize_text(c.get("email", ""))
        out[f"coach{idx}_phone"] = excel_protect_phone(c.get("phone", ""))

    return out
