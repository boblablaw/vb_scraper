# roster.py
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit
from io import StringIO

import requests
from bs4 import BeautifulSoup, Tag

from .logging_utils import get_logger
from .playwright_control import (
    PLAYWRIGHT_ENABLED,
    PLAYWRIGHT_PROFILE_FETCH_LIMIT,
    PLAYWRIGHT_PROFILE_FETCH_TIMEOUT_MS,
    PlaywrightTimeoutError,
    record_playwright_use,
    should_use_playwright,
    sync_playwright,
)
from .utils import normalize_text, fetch_html, normalize_class, canonical_name

logger = get_logger(__name__)

def _should_use_playwright() -> bool:
    if not should_use_playwright():
        if PLAYWRIGHT_ENABLED and PLAYWRIGHT_PROFILE_FETCH_LIMIT is not None:
            logger.debug(
                "Playwright profile fetch limit (%s) reached; skipping additional renders.",
                PLAYWRIGHT_PROFILE_FETCH_LIMIT,
            )
        return False
    return True

PLAYER_PHOTO_DIR = Path(__file__).resolve().parent.parent / "player_photos"
BIO_CHAR_LIMIT = 800

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


def _strip_location_label(value: str) -> str:
    return re.sub(r"^(Hometown|Last School)\s*", "", value, flags=re.IGNORECASE).strip()


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


def clean_position_height_noise(position: str) -> str:
    """
    Remove height patterns that sometimes appear at the end of position strings.
    Example: "Left Side LS 5'10\"" -> "Left Side LS"
    """
    if not position:
        return ""
    # Remove trailing height-like patterns: 5'10", 5-10, 6-2, etc.
    position = re.sub(r"\s*\d{1,2}['\'′][- ]?\d{1,2}[\"″]?\s*$", "", position)
    position = re.sub(r"\s*\d{1,2}[-]\d{1,2}\s*$", "", position)
    return position.strip()


def is_height_placeholder(height: str) -> bool:
    """
    Check if the height field contains placeholder text like "Jersey Number".
    """
    if not height:
        return False
    low = height.lower()
    return "jersey" in low or "number" in low


def looks_like_club_name(class_raw: str) -> bool:
    """
    Check if the class field looks like a volleyball club name instead of a class year.
    Keywords: club, volleyball, vbc, nation, team
    Returns True if it contains 'vbc' or at least 2 of the other keywords.
    """
    if not class_raw:
        return False
    low = class_raw.lower()
    
    # VBC is a strong signal
    if "vbc" in low:
        return True
    
    # Check for multiple club-related keywords
    keywords = ["club", "volleyball", "nation", "team"]
    count = sum(1 for kw in keywords if kw in low)
    return count >= 2


def is_impact_position(position: str) -> bool:
    """
    TEAM IMPACT entries often show up in the position field; skip those players.
    """
    return "impact" in (position or "").lower()


def is_impact_high_school(high_school: str) -> bool:
    """
    TEAM IMPACT entries sometimes appear in high school fields (e.g., 'Team IMPACT').
    """
    return "team impact" in (high_school or "").lower()


def filter_impact_players(players: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Remove TEAM IMPACT entries from a parsed player list."""
    filtered = [
        p for p in players
        if not is_impact_position(p.get("position", ""))
        and not is_impact_high_school(p.get("high_school", ""))
    ]
    removed = len(players) - len(filtered)
    if removed:
        logger.info("Filtered %d TEAM IMPACT entries from roster parse.", removed)
    return filtered

import re
from typing import Optional

def extract_personal_block(raw_text: str) -> Optional[str]:
    """
    Given the full bio text (like your examples), return the 'Personal' section
    as a single string, or None if there is no Personal block.

    It grabs everything after the word 'Personal' up until the next section
    header like 'Before BYU', 'Sophomore', etc.
    """
    pattern = re.compile(
        r"Personal"                        # literal heading
        r"(?P<personal>.*?)(?="            # lazily capture everything after it, up to…
        r"Before BYU|Sophomore|Freshman|"  # stop when any of these headers appear
        r"Junior|Senior|$)",               # …or end of string
        flags=re.IGNORECASE | re.DOTALL,
    )

    m = pattern.search(raw_text)
    if not m:
        return None

    # Clean up spacing a bit
    personal = m.group("personal").strip()
    # Optional: collapse multiple spaces
    personal = re.sub(r"\s+", " ", personal)
    return personal or None


def _extract_bio_from_text_block(text: str) -> str:
    """
    Roughly extract a bio from plain text by trimming navigation/headers and
    starting at the 'Bio' heading when present.
    """
    t = normalize_text(text)
    if not t:
        return ""
    lower = t.lower()

    # Drop leading navigation noise
    for marker in ("skip to main content", "scoreboard"):
        idx = lower.find(marker)
        if idx == 0:
            t = t[len(marker):].strip()
            lower = t.lower()

    bio_idx = lower.find("bio")
    if bio_idx != -1 and bio_idx < 800:
        t = t[bio_idx + len("bio"):].strip()
        lower = t.lower()
        t = re.sub(r"^\s*stats\s+media\s+", "", t, flags=re.IGNORECASE)

    if "athletics" in lower and lower.find("athletics") < 200:
        t = t[lower.find("athletics") + len("athletics"):].strip()
        lower = t.lower()

    stop_candidates = [
        lower.find("personal information"),
        lower.find("do not sell or share my personal information"),
    ]
    stop_candidates = [i for i in stop_candidates if i != -1]
    if stop_candidates:
        stop = min(stop_candidates)
        if stop > 0:
            t = t[:stop].strip()

    return t


def _extract_personal_from_dom(soup: BeautifulSoup) -> str:
    """
    Capture the Personal section from the DOM (heading + following content).
    Returns text with original capitalization.
    """
    if not soup:
        return ""

    stop_words = ("before byu", "career", "sophomore", "freshman", "junior", "senior", "season", "stats")
    headers = soup.find_all(["h2", "h3", "h4", "p", "strong", "div"])
    for header in headers:
        heading_text = normalize_text(header.get_text(" ", strip=True))
        if not heading_text or "personal" not in heading_text.lower():
            continue

        parts: List[str] = [heading_text]

        for sibling in header.next_siblings:
            if isinstance(sibling, str):
                continue
            if isinstance(sibling, Tag):
                sib_text = normalize_text(sibling.get_text(" ", strip=True))
                if not sib_text:
                    continue
                lower = sib_text.lower()
                if any(word in lower for word in stop_words):
                    break
                parts.append(sib_text)
                if sibling.name in ("h2", "h3", "h4"):
                    break

        if parts:
            return " ".join(parts)

    # Fallback to regex against full text
    full_text = normalize_text(soup.get_text(" ", strip=True))
    personal = extract_personal_block(full_text)
    return personal or ""


SCARD_CARD_SELECTORS = [
    ".s-person-card.s-person-card--list",
    ".s-person-card",
]

def _is_s_person_card_staff(card: Tag) -> bool:
    """
    Detect cards that belong to staff/coaching sections and skip them.
    """
    ancestor = card
    while isinstance(ancestor, Tag):
        ancestor_id = ancestor.get("id") or ""
        if isinstance(ancestor_id, str) and "coach" in ancestor_id.lower():
            return True
        for cls in ancestor.get("class") or []:
            if isinstance(cls, str) and "coaching-staff" in cls:
                return True
        ancestor = ancestor.parent if isinstance(ancestor.parent, Tag) else None
    if card.select_one(".s-person-card__content__contact-det"):
        return True
    text = normalize_text(card.get_text(" ", strip=True)).lower()
    if "coach" in text:
        return True
    return False


def _extract_s_person_card_player(card: Tag, base_url: str) -> Dict[str, str]:
    name_tag = card.select_one("h3")
    name = _clean(name_tag.get_text()) if name_tag else ""

    profile_link = (
        card.select_one("[data-test-id='s-person-details__thumbnail-link']")
        or card.select_one("[data-test-id='s-person-card-list__content-call-to-action-link']")
    )
    profile_url = profile_link.get("href") if profile_link and profile_link.get("href") else ""

    jersey_tag = card.select_one(".s-stamp__text")
    jersey = ""
    if jersey_tag:
        jersey = "".join(ch for ch in jersey_tag.get_text() if ch.isdigit())

    hometown_tag = card.select_one("[data-test-id='s-person-card-list__content-location-person-hometown']")
    high_school_tag = card.select_one("[data-test-id='s-person-card-list__content-location-person-high-school']")

    photo_tag = card.select_one('img[data-test-id="s-image-resized__img"]')
    photo_url = photo_tag.get("src") if photo_tag and photo_tag.get("src") else ""

    position_tag = card.select_one("[data-test-id='s-person-details__bio-stats-person-position-short']")
    class_tag = card.select_one("[data-test-id='s-person-details__bio-stats-person-title']")
    height_tag = card.select_one("[data-test-id='s-person-details__bio-stats-person-season']")

    return {
        "name": name,
        "position": _clean(position_tag.get_text()) if position_tag else "",
        "class_raw": _clean(class_tag.get_text()) if class_tag else "",
        "height_raw": _clean(height_tag.get_text()) if height_tag else "",
        "profile_url": profile_url,
        "jersey_number": jersey,
        "hometown": _strip_location_label(_clean(hometown_tag.get_text())) if hometown_tag else "",
        "high_school": _strip_location_label(_clean(high_school_tag.get_text())) if high_school_tag else "",
        "photo_url": urljoin(base_url, photo_url) if photo_url else "",
    }


def parse_s_person_card_layout(html: str, base_url: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(", ".join(SCARD_CARD_SELECTORS))
    cards = [card for card in cards if not _is_s_person_card_staff(card)]
    if not cards:
        return []

    players_map: Dict[str, Dict[str, str]] = {}
    canonical_order: List[str] = []
    for card in cards:
        player = _extract_s_person_card_player(card, base_url)
        profile_url = player.get("profile_url", "")
        if profile_url and "/roster/coaches/" in profile_url:
            continue
        player_name = player.get("name", "")
        canonical_name_sig = canonical_name(player_name or "")
        if not canonical_name_sig:
            continue
        existing = players_map.get(canonical_name_sig)
        if existing:
            if not existing.get("profile_url") and profile_url:
                players_map[canonical_name_sig] = player
            continue
        players_map[canonical_name_sig] = player
        canonical_order.append(canonical_name_sig)

    players = [players_map[name] for name in canonical_order]
    if players:
        logger.info("Parsed %d players from s-person-card layout.", len(players))
    return players


def _fetch_profile_html_with_playwright(url: str, timeout_ms: int = PLAYWRIGHT_PROFILE_FETCH_TIMEOUT_MS) -> Optional[str]:
    if not sync_playwright:
        return None
    record_playwright_use()
    html: Optional[str] = None
    browser = None
    context = None
    page = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            goto_timeout = max(timeout_ms, 45000)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout)
            except PlaywrightTimeoutError:
                logger.warning("Playwright timeout loading profile (partial HTML used): %s", url)
            # Some sites hide bio behind a tab; best-effort click the Bio tab
            try:
                page.get_by_role("tab", name="Bio").first.click(timeout=2500)
            except Exception:
                pass
            # Wait briefly for content to settle
            try:
                page.wait_for_selector(
                    ".s-bio-content, [data-test-id='s-tab-item-content'], .legacy_to_nextgen, .roster-bio__bio-content",
                    timeout=2500,
                )
            except Exception:
                page.wait_for_timeout(1000)
            html = page.content()
    except PlaywrightTimeoutError:
        logger.warning("Playwright timeout loading profile: %s", url)
    except Exception as exc:
        logger.debug("Playwright profile fetch failed: %s", exc)
    finally:
        try:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
        except Exception:
            pass
    return html


def _trim_to_personal_section(text: str) -> str:
    """
    Return text starting at the first 'Personal' heading (any case).
    Keeps the original capitalization from the source text.
    """
    if not text:
        return text
    m = re.search(r"personal", text, flags=re.IGNORECASE)
    if not m:
        return text
    # Prefer the bounded Personal block if we can find it
    personal_only = extract_personal_block(text)
    if personal_only:
        return personal_only.strip()
    return text[m.end():].strip()


def _strip_personal_label(text: str) -> str:
    """
    Remove a leading 'Personal' label if present.
    """
    if not text:
        return text
    return re.sub(r"^\s*personal[:\-]*\s*", "", text, flags=re.IGNORECASE)


def _looks_like_social_cta(text: str) -> bool:
    """
    Detect social-media CTA blobs (e.g., 'Follow Instagram...') that are not bios.
    """
    if not text:
        return False
    lowered = text.lower()
    keywords = (
        "follow instagram",
        "follow us",
        "opens in a new window",
        "facebook",
        "twitter",
        "x.com",
        "tiktok",
        "snapchat",
        "threads.net",
        "cookie policy",
        "privacy policy",
        "personal data",
        "personal information",
        "personalized ads",
        "consent to",
        "official athletics website",
        "women's volleyball 2025",
    )
    return any(k in lowered for k in keywords)


def _extract_bio_from_s_person_profile(html: str) -> str:
    # Temporarily disabled bio scraping; return empty string.
    return ""


def _extract_photo_from_profile_html(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    img = soup.select_one('img[data-test-id="s-image-resized__img"]')
    if not img:
        return ""
    src = img.get("data-src") or img.get("src") or ""
    return urljoin(base_url, src)


def _augment_profile_with_playwright(detail: Dict[str, str], profile_url: str) -> Dict[str, str]:
    if not profile_url or not _should_use_playwright():
        return detail
    rendered_html = _fetch_profile_html_with_playwright(profile_url)
    if not rendered_html:
        return detail
    # Bio scraping temporarily disabled.
    photo = _extract_photo_from_profile_html(rendered_html, profile_url)
    if photo and not detail.get("photo_url"):
        detail["photo_url"] = photo
    return detail


def parse_sidearm_player_profile(html: str, base_url: str = "") -> Dict[str, str]:
    """
    Parse a Sidearm player profile page for position / class / height.
    Some schools (e.g., Bradley) omit these on the roster list but include
    <dl><dd>value</dd><dt>Label</dt></dl> blocks on the player page.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style blobs that can pollute extracted text
    for bad in soup.find_all(["script", "style"]):
        bad.decompose()
    details: Dict[str, str] = {}

    def set_if_empty(key: str, value: str) -> None:
        val = normalize_text(value or "")
        if val and not details.get(key):
            details[key] = val

    # Common header fields on profile pages
    if not details.get("position"):
        pos_tag = soup.select_one(
            ".sidearm-roster-player-position, .sidearm-player-position, .roster-bio-position"
        )
        if pos_tag:
            set_if_empty("position", pos_tag.get_text())
    if not details.get("position"):
        # Some sites use a flex container with the sport appended
        pos_container = soup.select_one(".s-person-details__position div")
        if pos_container:
            set_if_empty("position", pos_container.get_text())

    if not details.get("class_raw"):
        class_tag = soup.select_one(
            ".sidearm-roster-player-academic-year, .sidearm-player-academic-year, .roster-bio-class"
        )
        if class_tag:
            set_if_empty("class_raw", class_tag.get_text())
    if not details.get("class_raw"):
        # Sidearm sometimes renders screen-reader-only label followed by value span
        for node in soup.find_all(string=lambda t: isinstance(t, str) and "Academic Year" in t):
            parent = node.parent
            sib = parent.find_next_sibling()
            if sib:
                set_if_empty("class_raw", sib.get_text())
                if details.get("class_raw"):
                    break

    if not details.get("height_raw"):
        height_tag = soup.select_one(
            ".sidearm-roster-player-height, .sidearm-player-height, .roster-bio-height"
        )
        if height_tag:
            set_if_empty("height_raw", height_tag.get_text())
    if not details.get("height_raw"):
        # Profile fields item blocks (e.g., <small class="profile-fields-item__label">Height</small><span class="profile-fields-item__value">6-0</span>)
        for label in soup.select(".profile-fields-item__label"):
            if normalize_text(label.get_text()).lower() == "height":
                val_tag = label.find_next_sibling(class_="profile-fields-item__value")
                if val_tag:
                    set_if_empty("height_raw", val_tag.get_text())
                    if details.get("height_raw"):
                        break
    # Profile fields generic parsing (position, class, hometown, high school)
    for label in soup.select(".profile-fields-item__label"):
        label_text = normalize_text(label.get_text())
        label_lower = label_text.lower()
        value_tag = label.find_next_sibling(class_="profile-fields-item__value")
        if not value_tag:
            continue
        value_text = normalize_text(value_tag.get_text())
        if not value_text:
            continue
        if "position" in label_lower and not details.get("position"):
            details["position"] = value_text
        elif ("class" in label_lower or "academic year" in label_lower) and not details.get("class_raw"):
            details["class_raw"] = value_text
        elif "hometown" in label_lower and not details.get("hometown"):
            details["hometown"] = value_text
        elif any(word in label_lower for word in ("high school", "previous school", "last school")) and not details.get("high_school"):
            details["high_school"] = value_text
        elif "height" in label_lower and not details.get("height_raw"):
            details["height_raw"] = value_text

    if not details.get("jersey_number"):
        jersey_tag = soup.select_one(
            ".sidearm-roster-player-jersey-number, .sidearm-player-jersey-number, .roster-bio-jersey-number, .s-person-details__jersey-number"
        )
        if jersey_tag:
            set_if_empty("jersey_number", jersey_tag.get_text())

    # Hometown / High School fallback selectors
    hometown_selectors = [
        ".sidearm-roster-player-hometown",
        ".roster-bio-hometown",
        ".s-person-details__hometown",
        ".profile-fields-item__value--hometown",
    ]
    for sel in hometown_selectors:
        tag = soup.select_one(sel)
        if tag:
            set_if_empty("hometown", tag.get_text())
            break

    hs_selectors = [
        ".sidearm-roster-player-highschool",
        ".sidearm-roster-player-high-school",
        ".roster-bio-highschool",
        ".profile-fields-item__value--highschool",
    ]
    for sel in hs_selectors:
        tag = soup.select_one(sel)
        if tag:
            set_if_empty("high_school", tag.get_text())
            break

    for dl in soup.find_all("dl"):
        label_tag = dl.find("dt")
        value_tag = dl.find("dd")
        if not label_tag or not value_tag:
            continue

        label = normalize_text(label_tag.get_text()).lower()
        value = normalize_text(value_tag.get_text())
        if not value:
            continue

        if "position" in label and "position" not in details:
            details["position"] = value
        elif ("class" in label or "academic year" in label) and "class_raw" not in details:
            details["class_raw"] = value
        elif "height" in label and "height_raw" not in details:
            details["height_raw"] = value
        elif "hometown" in label and "hometown" not in details:
            details["hometown"] = value
        elif ("high school" in label or "previous school" in label or "last school" in label) and "high_school" not in details:
            details["high_school"] = value
        elif "jersey" in label and "jersey_number" not in details:
            details["jersey_number"] = value

    # Bio text
    # Bio scraping temporarily disabled.

    # Player photo
    photo_selectors = [
        ".sidearm-roster-player-image img",
        ".sidearm-player-image img",
        ".roster-bio-image img",
        "img.sidearm-roster-player-image",
    ]
    photo_url = ""
    for sel in photo_selectors:
        img = soup.select_one(sel)
        if img and (img.get("src") or img.get("data-src")):
            photo_url = img.get("data-src") or img.get("src") or ""
            break
    if not photo_url:
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            photo_url = og.get("content")
    if photo_url:
        details["photo_url"] = urljoin(base_url, photo_url)

    return details


def enrich_from_player_profiles(players: List[Dict[str, str]], base_url: str) -> List[Dict[str, str]]:
    """
    For rosters that only list names, fetch individual player profile pages (when provided)
    to fill position / class / height and additional bio fields.
    """
    enriched = 0
    for p in players:
        needs_position = not p.get("position")
        needs_class = (not p.get("class_raw")) or (normalize_class(p.get("class_raw", "")) == "")
        needs_height = not p.get("height_raw")
        needs_extra = not (p.get("jersey_number") and p.get("hometown") and p.get("high_school"))
        needs_profile = not (p.get("bio") and p.get("photo_url"))
        if not (needs_position or needs_class or needs_height or needs_extra or needs_profile):
            continue

        profile_url = p.get("profile_url")
        if not profile_url:
            continue

        full_url = urljoin(base_url, profile_url)
        profile_html = None
        try:
            profile_html = fetch_html(full_url)
        except Exception as e:
            logger.debug("Could not fetch profile %s: %s", full_url, e)

        detail = parse_sidearm_player_profile(profile_html or "", base_url)
        detail = _augment_profile_with_playwright(detail, full_url)
        filled = False
        if needs_position and detail.get("position"):
            p["position"] = detail["position"]
            filled = True
        if needs_class and detail.get("class_raw"):
            p["class_raw"] = detail["class_raw"]
            filled = True
        if needs_height and detail.get("height_raw"):
            p["height_raw"] = detail["height_raw"]
            filled = True
        for key in ("jersey_number", "hometown", "high_school", "photo_url"):
            if detail.get(key) and not p.get(key):
                p[key] = detail[key]
                filled = True

        if filled:
            enriched += 1

    if enriched:
        logger.info("Enriched %d players from profile pages.", enriched)
    return players


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
        profile_url = ""
        if name_tag:
            if name_tag.name == "a" and name_tag.get("href"):
                profile_url = name_tag.get("href")
            else:
                link = name_tag.find("a", href=True)
                if link and link.get("href"):
                    profile_url = link.get("href")

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

        jersey_tag = (
            card.find(class_="sidearm-roster-player-jersey-number")
            or card.find(class_="sidearm-roster-player-jersey")
            or card.find(class_=re.compile("jersey", re.I))
        )
        jersey_number = _clean(jersey_tag.get_text()) if jersey_tag else ""

        if not name:
            continue

        # Clean data before adding to player list
        position = clean_position_height_noise(position)
        if is_height_placeholder(height_raw):
            height_raw = ""
        if looks_like_club_name(class_raw):
            class_raw = ""

        players.append(
            {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
                "profile_url": profile_url,
                "jersey_number": jersey_number,
            }
        )

    players = filter_impact_players(players)

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
        number_idx = find_col(["#", "number", "jersey"])

        if name_idx is None or pos_idx is None:
            continue

        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # Strip script/style blobs that can pollute text (e.g., injected __NUXT__ config)
            for c in cells:
                for bad in c.find_all(["script", "style"]):
                    bad.decompose()

            texts = [normalize_text(c.get_text()) for c in cells]

            def get(idx: Optional[int]) -> str:
                if idx is None:
                    return ""
                if 0 <= idx < len(texts):
                    return texts[idx]
                return ""

            name_cell = cells[name_idx] if name_idx is not None and name_idx < len(cells) else None
            name = normalize_text(name_cell.get_text()) if name_cell else ""
            profile_url = ""
            if name_cell:
                link = name_cell.find("a", href=True)
                if link and link.get("href"):
                    profile_url = link.get("href")
            position = get(pos_idx)
            class_raw = get(class_idx)
            height_raw = get(height_idx)
            jersey_raw = get(number_idx)
            jersey_number = ""
            if jersey_raw:
                jersey_number = "".join(ch for ch in jersey_raw if ch.isdigit())

            # Staff filter: skip obvious staff/coaches rows
            lower_row = " ".join(texts).lower()
            lower_pos = position.lower()
            
            # Skip if contains coach (but not if it's about volleyball coaching)
            if "coach" in lower_row and "volleyball" not in lower_row:
                continue
            
            # Skip if position contains staff keywords
            staff_keywords = ['director', 'coordinator', 'trainer', 'advisor', 'communications', 
                            'operations', 'strength', 'conditioning', 'manager', 'admin',
                            'video', 'creative']
            if any(kw in lower_pos for kw in staff_keywords):
                continue

            if not name:
                continue

            # Clean data before adding to player list
            position = clean_position_height_noise(position)
            if is_height_placeholder(height_raw):
                height_raw = ""
            if looks_like_club_name(class_raw):
                class_raw = ""

            players.append(
                {
                    "name": name,
                    "position": position,
                    "class_raw": class_raw,
                    "height_raw": height_raw,
                    "profile_url": profile_url,
                    "jersey_number": jersey_number,
                }
            )

    players = filter_impact_players(players)

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

        # Clean data before adding to player list
        position = clean_position_height_noise(position)
        if is_height_placeholder(height_raw):
            height_raw = ""
        if looks_like_club_name(class_raw):
            class_raw = ""

        players.append(
            {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
            }
        )

    players = filter_impact_players(players)

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

        # Clean data before adding to player list
        position_clean = clean_position_height_noise(_clean(position))
        class_raw_clean = _clean(class_raw)
        height_raw_clean = _clean(height_raw)
        if is_height_placeholder(height_raw_clean):
            height_raw_clean = ""
        if looks_like_club_name(class_raw_clean):
            class_raw_clean = ""

        players.append(
            {
                "name": name,
                "position": position_clean,
                "class_raw": class_raw_clean,
                "height_raw": height_raw_clean,
            }
        )

    # Filter out empty ones
    players = [p for p in players if p["name"]]

    players = filter_impact_players(players)

    if players:
        logger.info("Parsed %d players from heading-card roster.", len(players))

    return players


# ===================== WMT REFERENCE-BASED JSON ROSTER =====================


def parse_wmt_reference_json_roster(html: str, url: str) -> List[Dict[str, str]]:
    """
    Parse WMT/SIDEARM rosters that use a reference-based JSON system.
    
    Some sites (Auburn, other SEC schools) embed roster data in a large JSON array
    where data is stored as integer references pointing to other array indices.
    
    The structure looks like:
    - Main array with ~3000+ items
    - Item containing keys like "roster-{id}-players-list-page-1"
    - That references another item with 'players' key
    - 'players' references an array of player indices
    - Each player object has nested references to name, position, class, height
    
    Returns list of dicts: {"name", "position", "class_raw", "height_raw"}
    """
    players: List[Dict[str, str]] = []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script')
        
        # Look for large JSON arrays in script tags
        for script in scripts:
            if not script.string:
                continue
            
            script_text = script.string.strip()
            
            # Check if it looks like a large reference-based JSON
            if not (script_text.startswith('[') and 'roster' in script_text.lower() and len(script_text) > 50000):
                continue
            
            try:
                data = json.loads(script_text)
                if not isinstance(data, list) or len(data) < 1000:
                    continue
                
                logger.info("Found WMT reference-based JSON array with %d items", len(data))
                
                # Helper to resolve integer references
                def resolve(ref):
                    if isinstance(ref, int) and 0 <= ref < len(data):
                        return data[ref]
                    return ref
                
                # Find the roster reference key
                roster_ref = None
                for item in data[:100]:  # Check first 100 items
                    if isinstance(item, dict):
                        for key in item.keys():
                            if 'roster' in key and 'players-list' in key:
                                roster_ref = item.get(key)
                                logger.info("Found roster reference key: %s -> %s", key, roster_ref)
                                break
                        if roster_ref:
                            break
                
                if not roster_ref:
                    continue
                
                # Get roster object
                roster_obj = resolve(roster_ref)
                if not isinstance(roster_obj, dict) or 'players' not in roster_obj:
                    continue
                
                # Get players list
                players_list_ref = roster_obj['players']
                player_refs = resolve(players_list_ref)
                
                if not isinstance(player_refs, list):
                    continue
                
                logger.info("Found %d player references", len(player_refs))
                
                # Extract each player
                for player_ref in player_refs:
                    player_obj = resolve(player_ref)
                    if not isinstance(player_obj, dict):
                        continue
                    
                    # Resolve nested references
                    player_info = resolve(player_obj.get('player', {}))
                    position_obj = resolve(player_obj.get('player_position', {}))
                    class_obj = resolve(player_obj.get('class_level', {}))
                    def find_height(obj) -> str:
                        """
                        Best-effort height extractor when height_feet/height_inches are absent.
                        Looks for strings like 6-1 or 6'1 in any string values of the object.
                        """
                        if not isinstance(obj, dict):
                            return ""
                        import re
                        for v in obj.values():
                            if isinstance(v, str):
                                m = re.search(r"[4-7]['\\-]\\s?\\d{1,2}", v)
                                if m:
                                    return m.group(0).replace("'", "-").replace(" ", "")
                            elif isinstance(v, (int, float)):
                                # skip plain numbers
                                continue
                            elif isinstance(v, dict):
                                h = find_height(v)
                                if h:
                                    return h
                        return ""
                    
                    def find_height_loose(obj) -> str:
                        if not isinstance(obj, dict):
                            return ""
                        # common keys: height, height_feet_inches, heightInches
                        for k, v in obj.items():
                            lk = str(k).lower()
                            if "height" in lk:
                                if isinstance(v, str):
                                    if HEIGHT_RE.search(v):
                                        return HEIGHT_RE.search(v).group(0)
                                    m = re.search(r"[4-7]['\\-]\\s?\\d{1,2}", v)
                                    if m:
                                        return m.group(0).replace("'", "-").replace(" ", "")
                                elif isinstance(v, (int, float)):
                                    # single number can't give both feet/inches
                                    continue
                        return ""
                    
                    # Extract data with safe handling
                    first_name = resolve(player_info.get('first_name', '')) if isinstance(player_info, dict) else ''
                    last_name = resolve(player_info.get('last_name', '')) if isinstance(player_info, dict) else ''
                    name = _clean(f"{first_name} {last_name}".strip()) if first_name or last_name else ''
                    
                    if not name:
                        continue
                    
                    # Height
                    height_feet = resolve(player_obj.get('height_feet', ''))
                    height_inches = resolve(player_obj.get('height_inches', ''))
                    # Accept 0 inches as valid; only treat None/'' as missing
                    if height_feet not in (None, '') and height_inches not in (None, ''):
                        height_raw = f"{height_feet}-{height_inches}"
                    else:
                        height_raw = ''
                    if not height_raw:
                        height_raw = (
                            find_height(player_obj)
                            or find_height(player_info)
                            or find_height_loose(player_obj)
                            or find_height_loose(player_info)
                        )

                    profile_url = ""
                    if isinstance(player_info, dict):
                        profile_url = (
                            player_info.get("url")
                            or player_info.get("link")
                            or player_obj.get("url")
                            or player_obj.get("link")
                            or ""
                        )
                    
                    # Position
                    position = ''
                    if isinstance(position_obj, dict):
                        position = resolve(position_obj.get('name', '')) or ''
                    position = _clean(position)
                    
                    # Class (try abbreviation first, fall back to name)
                    class_raw = ''
                    if isinstance(class_obj, dict):
                        class_raw = resolve(class_obj.get('abbreviation', '')) or resolve(class_obj.get('name', '')) or ''
                    class_raw = _clean(class_raw)
                    
                    # Clean data
                    position = clean_position_height_noise(position)
                    if is_height_placeholder(height_raw):
                        height_raw = ""
                    if looks_like_club_name(class_raw):
                        class_raw = ""

                    jersey_candidates = [
                        resolve(player_obj.get("jersey_number")),
                        resolve(player_info.get("jersey_number")) if isinstance(player_info, dict) else "",
                        resolve(player_obj.get("jersey_number_label")),
                    ]
                    jersey_number = ""
                    for val in jersey_candidates:
                        if val not in (None, ""):
                            jersey_number = _clean(str(val))
                            if jersey_number:
                                break
                    hometown = _clean(resolve(player_info.get("hometown", ""))) if isinstance(player_info, dict) else ""
                    high_school = ""
                    if isinstance(player_info, dict):
                        high_school = _clean(
                            resolve(player_info.get("high_school") or player_info.get("previous_school") or "")
                        )
                    photo_url = ""
                    photo_obj = resolve(player_obj.get("photo"))
                    if isinstance(photo_obj, dict):
                        photo_url = _clean(resolve(photo_obj.get("url", "")) or "")
                    if not photo_url and isinstance(player_info, dict):
                        master_photo = resolve(player_info.get("master_photo"))
                        if isinstance(master_photo, dict):
                            photo_url = _clean(resolve(master_photo.get("url", "")) or "")
                    profile_url = ""
                    slug = ""
                    if isinstance(player_info, dict):
                        slug = _clean(resolve(player_info.get("slug", "")))
                    if slug:
                        # Keep relative slug; team_analysis will urljoin with roster_url if needed
                        profile_url = slug
                    
                    players.append({
                        "name": name,
                        "position": position,
                        "class_raw": class_raw,
                        "height_raw": height_raw,
                        "profile_url": profile_url,
                        "jersey_number": jersey_number,
                        "hometown": hometown,
                        "high_school": high_school,
                        "photo_url": photo_url,
                    })
                
                if players:
                    players = filter_impact_players(players)
                    if players:
                        logger.info("Parsed %d players from WMT reference-based JSON", len(players))
                    return players
                    
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.debug("Failed to parse WMT reference JSON: %s", e)
                continue
        
    except Exception as e:
        logger.debug("Error in WMT reference JSON parser: %s", e)
    
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
                        if height_feet is not None and height_inches is not None:
                            height_raw = f"{height_feet}-{height_inches}"
                        
                        # Extract class/year
                        class_raw = _clean(
                            obj.get('academic_year_short', '')
                            or obj.get('academic_year_long', '')
                            or obj.get('class', '')
                        )
                        
                        # Clean data before adding to player list
                        position = clean_position_height_noise(position)
                        if is_height_placeholder(height_raw):
                            height_raw = ""
                        if looks_like_club_name(class_raw):
                            class_raw = ""
                        
                        players.append({
                            "name": name,
                            "position": position,
                            "class_raw": class_raw,
                            "height_raw": height_raw,
                        })
                    
                    if players:
                        players = filter_impact_players(players)
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
            # Skip navigation/breadcrumb JSON (e.g., Coastal Carolina, Le Moyne)
            # These have @type: 'ListItem' or contain institutional keywords
            obj_type = obj.get("@type", "")
            if obj_type in ("ListItem", "BreadcrumbList", "SearchAction"):
                return None
            
            name = _clean(
                obj.get("name")
                or obj.get("full_name")
                or obj.get("athlete_name")
                or ""
            )
            if not name:
                return None
            
            # Filter out names that are clearly institutional/navigation text
            name_lower = name.lower()
            institutional_keywords = [
                "athletics", "recreation", "college", "university", 
                "roster", "degree program", "community college"
            ]
            if any(kw in name_lower for kw in institutional_keywords):
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
            
            # Clean data before returning
            position = clean_position_height_noise(position)
            if is_height_placeholder(height_raw):
                height_raw = ""
            if looks_like_club_name(class_raw):
                class_raw = ""
            
            return {
                "name": name,
                "position": position,
                "class_raw": class_raw,
                "height_raw": height_raw,
                "profile_url": obj.get("url", ""),
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
        players = filter_impact_players(players)
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


LOCATION_CONTINUATION_RE = re.compile(
    r"(,|\b(high school|academy|prep(?: school)?|school|hs)\b)", re.IGNORECASE
)

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

STATE_MAP = {
    "alabama": "Alabama",
    "al": "Alabama",
    "alaska": "Alaska",
    "ak": "Alaska",
    "arizona": "Arizona",
    "az": "Arizona",
    "arkansas": "Arkansas",
    "ar": "Arkansas",
    "california": "California",
    "ca": "California",
    "colorado": "Colorado",
    "co": "Colorado",
    "connecticut": "Connecticut",
    "ct": "Connecticut",
    "delaware": "Delaware",
    "de": "Delaware",
    "florida": "Florida",
    "fl": "Florida",
    "georgia": "Georgia",
    "ga": "Georgia",
    "hawaii": "Hawaii",
    "hi": "Hawaii",
    "idaho": "Idaho",
    "id": "Idaho",
    "illinois": "Illinois",
    "il": "Illinois",
    "indiana": "Indiana",
    "in": "Indiana",
    "iowa": "Iowa",
    "ia": "Iowa",
    "kansas": "Kansas",
    "ks": "Kansas",
    "kentucky": "Kentucky",
    "ky": "Kentucky",
    "louisiana": "Louisiana",
    "la": "Louisiana",
    "maine": "Maine",
    "me": "Maine",
    "maryland": "Maryland",
    "md": "Maryland",
    "massachusetts": "Massachusetts",
    "ma": "Massachusetts",
    "michigan": "Michigan",
    "mi": "Michigan",
    "minnesota": "Minnesota",
    "mn": "Minnesota",
    "mississippi": "Mississippi",
    "ms": "Mississippi",
    "missouri": "Missouri",
    "mo": "Missouri",
    "montana": "Montana",
    "mt": "Montana",
    "nebraska": "Nebraska",
    "ne": "Nebraska",
    "nevada": "Nevada",
    "nv": "Nevada",
    "new hampshire": "New Hampshire",
    "nh": "New Hampshire",
    "new jersey": "New Jersey",
    "nj": "New Jersey",
    "new mexico": "New Mexico",
    "nm": "New Mexico",
    "new york": "New York",
    "ny": "New York",
    "north carolina": "North Carolina",
    "nc": "North Carolina",
    "north dakota": "North Dakota",
    "nd": "North Dakota",
    "ohio": "Ohio",
    "oh": "Ohio",
    "oklahoma": "Oklahoma",
    "ok": "Oklahoma",
    "oregon": "Oregon",
    "or": "Oregon",
    "pennsylvania": "Pennsylvania",
    "pa": "Pennsylvania",
    "rhode island": "Rhode Island",
    "ri": "Rhode Island",
    "south carolina": "South Carolina",
    "sc": "South Carolina",
    "south dakota": "South Dakota",
    "sd": "South Dakota",
    "tennessee": "Tennessee",
    "tn": "Tennessee",
    "texas": "Texas",
    "tx": "Texas",
    "utah": "Utah",
    "ut": "Utah",
    "vermont": "Vermont",
    "vt": "Vermont",
    "virginia": "Virginia",
    "va": "Virginia",
    "washington": "Washington",
    "wa": "Washington",
    "west virginia": "West Virginia",
    "wv": "West Virginia",
    "wisconsin": "Wisconsin",
    "wi": "Wisconsin",
    "wyoming": "Wyoming",
    "wy": "Wyoming",
    "district of columbia": "District of Columbia",
    "dc": "District of Columbia",
}
STATE_KEYS = sorted(STATE_MAP.keys(), key=len, reverse=True)
HS_KEYWORD_RE = re.compile(
    r"\b(high school|academy|prep(?: school)?|school|hs)\b", re.IGNORECASE
)


def _extract_profile_url_from_node(node) -> str:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent.name == "a" and parent.get("href"):
            return parent["href"]
        parent = getattr(parent, "parent", None)
    return ""


def _split_state_from_text(text: str) -> tuple[str, str]:
    remainder = text.strip()
    if not remainder:
        return "", ""
    lower = remainder.lower()
    for key in STATE_KEYS:
        if lower.startswith(key) and (
            len(remainder) == len(key) or remainder[len(key)] in {" ", ","}
        ):
            after = remainder[len(key) :].strip(" ,")
            return STATE_MAP[key], after
    return "", remainder


def _split_location_details(text: str) -> tuple[str, str]:
    details = text.strip()
    if not details:
        return "", ""
    if "," in details:
        city, remainder = [part.strip() for part in details.split(",", 1)]
        state_name, after_state = _split_state_from_text(remainder)
        if state_name:
            hometown = f"{city}, {state_name}"
            high_school = after_state
            return hometown, high_school
    match = HS_KEYWORD_RE.search(details)
    if match:
        high_school = details[match.start() :].strip(" ,")
        hometown = details[: match.start()].strip(" ,")
        return hometown, high_school
    return details, ""


LOCATION_CONTINUATION_RE = re.compile(
    r"(,|\b(high school|academy|prep(?: school)?|school|hs)\b)", re.IGNORECASE
)

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

STATE_MAP = {
    "alabama": "Alabama",
    "al": "Alabama",
    "alaska": "Alaska",
    "ak": "Alaska",
    "arizona": "Arizona",
    "az": "Arizona",
    "arkansas": "Arkansas",
    "ar": "Arkansas",
    "california": "California",
    "ca": "California",
    "colorado": "Colorado",
    "co": "Colorado",
    "connecticut": "Connecticut",
    "ct": "Connecticut",
    "delaware": "Delaware",
    "de": "Delaware",
    "florida": "Florida",
    "fl": "Florida",
    "georgia": "Georgia",
    "ga": "Georgia",
    "hawaii": "Hawaii",
    "hi": "Hawaii",
    "idaho": "Idaho",
    "id": "Idaho",
    "illinois": "Illinois",
    "il": "Illinois",
    "indiana": "Indiana",
    "in": "Indiana",
    "iowa": "Iowa",
    "ia": "Iowa",
    "kansas": "Kansas",
    "ks": "Kansas",
    "kentucky": "Kentucky",
    "ky": "Kentucky",
    "louisiana": "Louisiana",
    "la": "Louisiana",
    "maine": "Maine",
    "me": "Maine",
    "maryland": "Maryland",
    "md": "Maryland",
    "massachusetts": "Massachusetts",
    "ma": "Massachusetts",
    "michigan": "Michigan",
    "mi": "Michigan",
    "minnesota": "Minnesota",
    "mn": "Minnesota",
    "mississippi": "Mississippi",
    "ms": "Mississippi",
    "missouri": "Missouri",
    "mo": "Missouri",
    "montana": "Montana",
    "mt": "Montana",
    "nebraska": "Nebraska",
    "ne": "Nebraska",
    "nevada": "Nevada",
    "nv": "Nevada",
    "new hampshire": "New Hampshire",
    "nh": "New Hampshire",
    "new jersey": "New Jersey",
    "nj": "New Jersey",
    "new mexico": "New Mexico",
    "nm": "New Mexico",
    "new york": "New York",
    "ny": "New York",
    "north carolina": "North Carolina",
    "nc": "North Carolina",
    "north dakota": "North Dakota",
    "nd": "North Dakota",
    "ohio": "Ohio",
    "oh": "Ohio",
    "oklahoma": "Oklahoma",
    "ok": "Oklahoma",
    "oregon": "Oregon",
    "or": "Oregon",
    "pennsylvania": "Pennsylvania",
    "pa": "Pennsylvania",
    "rhode island": "Rhode Island",
    "ri": "Rhode Island",
    "south carolina": "South Carolina",
    "sc": "South Carolina",
    "south dakota": "South Dakota",
    "sd": "South Dakota",
    "tennessee": "Tennessee",
    "tn": "Tennessee",
    "texas": "Texas",
    "tx": "Texas",
    "utah": "Utah",
    "ut": "Utah",
    "vermont": "Vermont",
    "vt": "Vermont",
    "virginia": "Virginia",
    "va": "Virginia",
    "washington": "Washington",
    "wa": "Washington",
    "west virginia": "West Virginia",
    "wv": "West Virginia",
    "wisconsin": "Wisconsin",
    "wi": "Wisconsin",
    "wyoming": "Wyoming",
    "wy": "Wyoming",
    "district of columbia": "District of Columbia",
    "dc": "District of Columbia",
}
STATE_KEYS = sorted(STATE_MAP.keys(), key=len, reverse=True)
HS_KEYWORD_RE = re.compile(
    r"\b(high school|academy|prep(?: school)?|school|hs)\b", re.IGNORECASE
)


def _split_state_from_text(text: str) -> tuple[str, str]:
    remainder = text.strip()
    if not remainder:
        return "", ""
    lower = remainder.lower()
    for key in STATE_KEYS:
        if lower.startswith(key) and (
            len(remainder) == len(key) or remainder[len(key)] in {" ", ","}
        ):
            after = remainder[len(key) :].strip(" ,")
            return STATE_MAP[key], after
    return "", remainder


def _split_location_details(details: str) -> tuple[str, str]:
    if not details:
        return "", ""
    parts = details.strip().split(",", 1)
    if len(parts) == 2:
        city = parts[0].strip()
        state_rest = parts[1].strip()
        state_name, after_state = _split_state_from_text(state_rest)
        if state_name:
            hometown = f"{city}, {state_name}"
            high_school = after_state
            return hometown.strip(" ,"), high_school.strip(" ,")

    match = HS_KEYWORD_RE.search(details)
    if match:
        high_school = details[match.start() :].strip(" ,")
        hometown = details[: match.start()].strip(" ,")
        return hometown, high_school

    return details.strip(), ""


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

    We return dicts with: name, position, class_raw, height_raw, jersey_number,
    hometown, high_school.
    """
    def parse_details_line(details: str) -> Optional[Dict[str, str]]:
        tokens = details.split()
        if not tokens:
            return None

        height_idx: Optional[int] = None
        for idx, tok in enumerate(tokens):
            if HEIGHT_RE.match(tok):
                height_idx = idx
                break

        if height_idx is None:
            return None

        position = " ".join(tokens[:height_idx]).strip()
        height = tokens[height_idx].strip()

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

    lines = [
        (normalize_text(str(text)), text)
        for text in soup.stripped_strings
        if normalize_text(text)
    ]
    players: List[Dict[str, str]] = []
    i = 0
    n = len(lines)

    while i < n - 2:
        jersey_line = lines[i][0]
        jersey = jersey_line.lstrip("#")
        if jersey.isdigit() and 1 <= len(jersey) <= 2:
            name_text, name_node = lines[i + 1]
            details = lines[i + 2][0]
            parsed = parse_details_line(details)
            if parsed and name_text:
                location_parts = [details]
                peek = i + 3
                while peek < n and LOCATION_CONTINUATION_RE.search(lines[peek][0]):
                    location_parts.append(lines[peek][0])
                    peek += 1
                location_str = " ".join(location_parts)
                hometown, high_school = _split_location_details(location_str)

                position = clean_position_height_noise(parsed["position"])
                height_raw = parsed["height_raw"]
                class_raw = parsed["class_raw"]
                if is_height_placeholder(height_raw):
                    height_raw = ""
                if looks_like_club_name(class_raw):
                    class_raw = ""

                profile_url = _extract_profile_url_from_node(name_node)

                players.append(
                    {
                        "name": name_text,
                        "position": position,
                        "class_raw": class_raw,
                        "height_raw": height_raw,
                        "profile_url": profile_url,
                        "jersey_number": jersey,
                        "hometown": hometown,
                        "high_school": high_school,
                    }
                )
                i = max(peek, i + 3)
                continue
        i += 1

    players = filter_impact_players(players)
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
            if pos_idx is not None and (not position or position.strip() == ""):
                pos_cell = cells[pos_idx]
                parts = [
                    s
                    for s in pos_cell.stripped_strings
                    if s.lower() not in {"position", "pos", "pos."}
                ]
                position = " ".join(parts)
            class_raw = get(class_idx)
            height_raw = get(height_idx)

            if not name:
                continue

            # Clean data before adding to player list
            position = clean_position_height_noise(position)
            if is_height_placeholder(height_raw):
                height_raw = ""
            if looks_like_club_name(class_raw):
                class_raw = ""

            players.append(
                {
                    "name": name,
                    "position": position,
                    "class_raw": class_raw,
                    "height_raw": height_raw,
                    "profile_url": profile_url,
                }
            )

    players = filter_impact_players(players)

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
      5) WMT reference-based JSON (Auburn, SEC schools)
      6) Embedded JSON roster
      7) Number / name / details text roster (BYU and similar)
      8) Very generic roster tables
      9) Optional WMT text enrichment + height back-fill.

    Returns list of dicts:
      { "name", "position", "class_raw", "height_raw" }
    """
    soup = BeautifulSoup(html, "html.parser")

    players = parse_s_person_card_layout(html, url)
    if not players:
        players = parse_sidearm_card_layout(soup)

    # 1) SIDEARM / NextGen cards
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

    # 5) WMT reference-based JSON (Auburn, SEC schools)
    if not players:
        logger.info("Trying WMT reference-based JSON parser for %s ...", url)
        players = parse_wmt_reference_json_roster(html, url)



    # 6) Embedded JSON blobs
    if not players:
        logger.info("Fallback: trying embedded JSON roster for %s ...", url)
        players = parse_roster_from_sidearm_json(html, url)

    # 6b) Tabular roster fallback (e.g., UNCBears) where names may be slugs or missing
    def parse_tabular_roster_fallback(html_text: str) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        try:
            tables = pd.read_html(StringIO(html_text))
        except Exception:
            return out
        for t in tables:
            cols = [str(c).lower() for c in t.columns]
            has_class = any("academic" in c or c == "yr" for c in cols)
            has_height = any("ht" in c or "height" in c for c in cols)
            has_pos = any("pos" in c for c in cols)
            if not (has_class and has_height and has_pos):
                continue
            name_col = None
            for c in t.columns:
                lc = str(c).lower()
                if "name" in lc or "player" in lc:
                    name_col = c
                    break
            if name_col is None:
                for slug_col in t.columns:
                    lc = str(slug_col).lower()
                    if "instagram" in lc or "inflcr" in lc:
                        def slug_to_name(x):
                            if not isinstance(x, str):
                                return ""
                            parts = x.replace("-", " ").split()
                            return " ".join(p.capitalize() for p in parts)
                        t["name"] = t[slug_col].apply(slug_to_name)
                        name_col = "name"
                        break
            if name_col is None:
                continue
                for _, row in t.iterrows():
                    name_val = str(row.get(name_col, "")).strip()
                    if not name_val:
                        continue
                    player = {
                        "name": name_val,
                        "number": row.get("#") or row.get("number") or "",
                        "position": row.get("Pos.") or row.get("pos") or row.get("Pos") or "",
                        "class_raw": row.get("Academic Year") or row.get("yr") or row.get("Year") or "",
                        "height_raw": row.get("Ht.") or row.get("Ht") or row.get("height") or "",
                    }
                    out.append(player)
            if out:
                return out
        return out

    # If we parsed very few players (<10), attempt tabular fallback once
    if players and len(players) < 10:
        tab_players = parse_tabular_roster_fallback(html)
        if tab_players:
            logger.info(
                "Replacing %d parsed players with %d from tabular roster fallback",
                len(players),
                len(tab_players),
            )
            players = tab_players

    # 7) Number / name / details text roster (BYU-style list/table view)
    if not players:
        logger.info(
            "No structured roster found for %s; trying number-name-details text fallback.",
            url,
        )
        players = parse_number_name_details_roster(soup)

    # 8) Very generic roster tables as absolute last resort
    if not players:
        players = parse_generic_table_roster(soup)

    if not players:
        logger.warning("No players parsed from roster %s.", url)
        return players

    # 9a) Optional: WMT-specific text enrichment if we only have names
    # Optional enrichment from player profile pages when only names are present
    if any(
        (
            not p.get("position")
            or not p.get("class_raw")
            or not p.get("height_raw")
            or not p.get("bio")
            or not p.get("photo_url")
        )
        and p.get("profile_url")
        for p in players
    ):
        players = enrich_from_player_profiles(players, url)

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
