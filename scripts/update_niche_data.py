#!/usr/bin/env python3
"""
Update Niche data in settings/teams.json using each team's niche_data_slug.

For every team entry:
  - Fetch https://www.niche.com/colleges/<slug>/
  - Parse overall_grade, academics_grade, value_grade, summary
  - Fetch reviews page and grab first two review bodies as review_pos/review_neg

Writes updated teams.json in place (with pretty indent).
"""
from __future__ import annotations

import argparse
import json
import re
import time
import os
import html
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
TEAMS_PATH = ROOT / "settings" / "teams.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vb-scraper-niche/1.0)"
}
COOKIE_STR: Optional[str] = None
BROWSER_PROVIDER: Optional[str] = None
BROWSER = None
BROWSER_CTX = None
BROWSER_PAGE = None
FORCE_BROWSER = False
VERBOSE = False
RENDER_WAIT_MS = 4000


def log(msg: str):
    if VERBOSE:
        print(msg)

# ------------------------- Browser management -------------------------
def close_browser():
    global BROWSER, BROWSER_CTX, BROWSER_PAGE
    try:
        if BROWSER_CTX:
            BROWSER_CTX.close()
    except Exception:
        pass
    try:
        if BROWSER:
            BROWSER.close()
    except Exception:
        pass
    BROWSER = None
    BROWSER_CTX = None
    BROWSER_PAGE = None


def ensure_browser(headless: bool = True, proxy: Optional[str] = None):
    """
    Lazily create or return a shared browser page (playwright > undetected).
    Keeps the window open for visibility in headful mode.
    """
    global BROWSER_PROVIDER, BROWSER, BROWSER_CTX, BROWSER_PAGE
    if BROWSER_PAGE:
        try:
            _ = BROWSER_PAGE.title()
            return BROWSER_PAGE
        except Exception:
            pass  # will recreate

    provider = None
    if PLAYWRIGHT_AVAILABLE:
        provider = "playwright"
    elif UND_PLAYWRIGHT_AVAILABLE:
        provider = "undetected"
    else:
        return None

    if provider == "playwright":
        with sync_playwright() as p:
            # NOTE: cannot use context manager return outside; so we need to launch directly
            pass
    # We can't use a context manager with return; implement explicit open below
    if provider == "playwright":
        try:
            import playwright.sync_api as psa
            p = psa.sync_playwright().start()
            launch_args = {
                "headless": headless,
                "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            }
            if proxy:
                launch_args["proxy"] = {"server": proxy}
            BROWSER = p.chromium.launch(**launch_args)
            ctx_headers = {"Accept-Language": "en-US,en;q=0.9"}
            if COOKIE_STR:
                ctx_headers["Cookie"] = COOKIE_STR
            BROWSER_CTX = BROWSER.new_context(user_agent=HEADERS["User-Agent"], extra_http_headers=ctx_headers)
            if COOKIE_STR:
                cookies = []
                # domain set per-visit in browser_fetch
                BROWSER_CTX._extra_cookies = COOKIE_STR  # stash string for later domain application
            BROWSER_PAGE = BROWSER_CTX.new_page()
            BROWSER_PROVIDER = "playwright"
            return BROWSER_PAGE
        except Exception as e:
            if VERBOSE:
                print(f"[browser] playwright launch failed: {e}")
            close_browser()
            return None

    if provider == "undetected":
        try:
            p = up.sync_playwright().start()  # type: ignore
            launch_args = {
                "headless": headless,
                "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            }
            if proxy:
                launch_args["proxy"] = {"server": proxy}
            BROWSER = p.chromium.launch(**launch_args)
            ctx_headers = {"Accept-Language": "en-US,en;q=0.9"}
            if COOKIE_STR:
                ctx_headers["Cookie"] = COOKIE_STR
            BROWSER_CTX = BROWSER.new_context(user_agent=HEADERS["User-Agent"], extra_http_headers=ctx_headers)
            if COOKIE_STR:
                BROWSER_CTX._extra_cookies = COOKIE_STR  # stash
            BROWSER_PAGE = BROWSER_CTX.new_page()
            BROWSER_PROVIDER = "undetected"
            return BROWSER_PAGE
        except Exception as e:
            if VERBOSE:
                print(f"[browser] undetected launch failed: {e}")
            close_browser()
            return None

    return None


def apply_cookies_to_context(ctx, url: str):
    """Attach cookies parsed from COOKIE_STR to the context for the given domain."""
    if not COOKIE_STR or not ctx:
        return
    try:
        domain = "." + urlparse(url).hostname.split(":", 1)[0]
    except Exception:
        return
    cookies = []
    for part in COOKIE_STR.split(";"):
        if "=" not in part:
            continue
        name, val = part.split("=", 1)
        cookies.append(
            {
                "name": name.strip(),
                "value": val.strip(),
                "domain": domain,
                "path": "/",
            }
        )
    if cookies:
        try:
            ctx.add_cookies(cookies)
        except Exception:
            pass


def browser_fetch(
    url: str,
    headless: bool = True,
    proxy: Optional[str] = None,
    captcha_pause: bool = False,
    wait_selectors: Optional[list[str]] = None,
    timeout_ms: int = 120000,
) -> Optional[str]:
    page = ensure_browser(headless=headless, proxy=proxy)
    if not page:
        return None

    # Ensure cookies set for this domain (once per domain)
    try:
        apply_cookies_to_context(page.context, url)
    except Exception:
        pass

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms // 2)
        except Exception:
            pass
    except Exception as e:
        if VERBOSE:
            print(f"[browser] goto error for {url}: {e}")

    if captcha_pause:
        input("Solve any captcha in the opened browser, then press Enter to continue...")
    else:
        if wait_selectors:
            for sel in wait_selectors:
                try:
                    page.wait_for_selector(sel, timeout=timeout_ms // 2)
                    break
                except Exception:
                    continue
        page.wait_for_timeout(RENDER_WAIT_MS)
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(RENDER_WAIT_MS)
        except Exception:
            pass

    try:
        content = page.content()
        return content
    except Exception:
        return None

# Optional Playwright fallback (only used if 403 encountered and module available)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False

# Optional undetected-playwright fallback (stealthier chromium)
try:
    import undetected_playwright as up  # type: ignore
    UND_PLAYWRIGHT_AVAILABLE = True
except Exception:
    UND_PLAYWRIGHT_AVAILABLE = False

# Politics scoring (mirrors existing helper script)
POLITICS_WEIGHTS = {
    "very conservative": -2.0,
    "conservative": -1.0,
    "moderate": 0.0,
    "moderate / independent": 0.0,
    "balanced": 0.0,
    "liberal": 1.0,
    "very liberal": 2.0,
}
POLL_LABELS = [
    "very conservative",
    "conservative",
    "moderate",
    "balanced",
    "liberal",
    "very liberal",
]


def fetch_html(url: str, force_browser: Optional[bool] = None) -> Optional[str]:
    if force_browser is None:
        force_browser = FORCE_BROWSER
    if force_browser:
        return None
    try:
        headers = dict(HEADERS)
        if COOKIE_STR:
            headers["Cookie"] = COOKIE_STR
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException:
        return None
    finally:
        if VERBOSE:
            method = "requests (skipped)" if force_browser else "requests"
            print(f"[FETCH] {url} via {method} -> {'OK' if 'resp' in locals() and resp.ok else 'FAIL'}")


def fetch_html_playwright(url: str, headless: bool = True, proxy: Optional[str] = None, captcha_pause: bool = False, timeout_ms: int = 120000, wait_selectors: Optional[list[str]] = None) -> Optional[str]:
    """
    Legacy helper: now delegates to shared browser_fetch when playwright is available.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    return browser_fetch(url, headless=headless, proxy=proxy, captcha_pause=captcha_pause, wait_selectors=wait_selectors, timeout_ms=timeout_ms)


def fetch_html_undetected(url: str, headless: bool = True, proxy: Optional[str] = None, captcha_pause: bool = False, timeout_ms: int = 120000, wait_selectors: Optional[list[str]] = None) -> Optional[str]:
    """
    Legacy helper: delegates to shared browser_fetch when undetected-playwright is available.
    """
    if not UND_PLAYWRIGHT_AVAILABLE:
        return None
    return browser_fetch(url, headless=headless, proxy=proxy, captcha_pause=captcha_pause, wait_selectors=wait_selectors, timeout_ms=timeout_ms)


def extract_grade(text: str, label: str) -> str:
    m = re.search(rf"{label}\s*([A-F][+-]?)", text, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_overall_grade(soup: BeautifulSoup) -> str:
    # Niche shows letter grade prominently; capture first standalone grade token.
    m = re.search(r"\b([A-F][+-]?)\b\s*Overall\s+Grade", soup.get_text(" ", strip=True))
    if m:
        return m.group(1)
    # fallback: first grade badge in page
    badge = soup.find(string=re.compile(r"^[A-F][+-]?$"))
    return badge.strip() if badge else ""


def extract_summary(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    # fallback: first paragraph of main content
    p = soup.find("p")
    return p.get_text(strip=True) if p else ""


def extract_reviews(
    slug: str,
    headless: bool = True,
    proxy: Optional[str] = None,
    captcha_pause: bool = False,
    force_browser: bool = False,
) -> tuple[str, str]:
    """Fetch the /reviews/ page for a given slug and return (pos, neg) review bodies.

    Uses the shared browser_fetch when needed so that headful mode and
    captcha_pulse work the same way as for the main and /students pages.
    """
    url = f"https://www.niche.com/colleges/{slug}/reviews/"
    log(f"[REVIEWS] fetch {url} (force_browser={force_browser})")

    # Try a simple HTTP fetch first unless we're forcing the browser
    html = fetch_html(url, force_browser=force_browser)
    if not html:
        log("[REVIEWS] falling back to browser_fetch")
        html = browser_fetch(
            url,
            headless=headless,
            proxy=proxy,
            captcha_pause=captcha_pause,
            wait_selectors=[
                '[itemprop="reviewBody"]',
                "text=Review",
            ],
        )

    if html:
        # Save a copy so we can inspect stubborn pages like Binghamton later
        save_debug_html(f"{slug}_reviews", html)
        # Also save the embedded __NEXT_DATA__ JSON for the reviews route
        save_next_data_json_from_html(slug, "reviews", html)
    if not html:
        return "", ""

    soup = BeautifulSoup(html, "html.parser")
    bodies: list[str] = []

    # Try structured review bodies
    for tag in soup.find_all(attrs={"itemprop": "reviewBody"}):
        txt = tag.get_text(" ", strip=True)
        if txt:
            bodies.append(txt)
        if len(bodies) >= 2:
            break

    # Fallback to generic paragraphs if nothing found
    if not bodies:
        for p in soup.find_all("p"):
            txt = p.get_text(" ", strip=True)
            if txt:
                bodies.append(txt)
            if len(bodies) >= 2:
                break

    pos = bodies[0] if bodies else ""
    neg = bodies[1] if len(bodies) > 1 else ""
    return pos, neg


# ------------------------- Niche enrichment helpers -------------------------

def extract_jsonld_college_data(soup: BeautifulSoup) -> dict:
    """Best-effort parse of the CollegeOrUniversity JSON-LD block on a Niche page.

    Returns a dict that may contain:
      street, city, state, zip_code, phone, website, rating_value, rating_count.
    """
    info: dict = {}
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            data = json.loads(raw)
        except Exception:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") != "CollegeOrUniversity":
                continue

            addr = obj.get("address") or {}
            info["street"] = (addr.get("streetAddress") or "").strip()
            info["city"] = (addr.get("addressLocality") or "").title()
            info["state"] = (addr.get("addressRegion") or "").upper()
            info["zip_code"] = (addr.get("postalCode") or "").strip()

            info["phone"] = (obj.get("telephone") or "").strip()
            info["website"] = (obj.get("sameAs") or obj.get("url") or "").strip()

            agg = obj.get("aggregateRating") or {}
            try:
                info["rating_value"] = float(agg.get("ratingValue"))
            except Exception:
                pass
            try:
                info["rating_count"] = int(agg.get("reviewCount"))
            except Exception:
                pass

            return info

    return info


def extract_meta_lat_lon(soup: BeautifulSoup) -> dict:
    """Extract latitude/longitude from Open Graph place meta tags if present."""
    out: dict = {}
    meta_lat = soup.find("meta", attrs={"property": "place:location:latitude"})
    meta_lon = soup.find("meta", attrs={"property": "place:location:longitude"})

    if meta_lat and meta_lat.get("content"):
        try:
            out["lat"] = float(meta_lat["content"])
        except Exception:
            pass
    if meta_lon and meta_lon.get("content"):
        try:
            out["lon"] = float(meta_lon["content"])
        except Exception:
            pass

    return out


def extract_median_earnings_5y(text: str) -> Optional[int]:
    """Parse the 'Median earnings 5 years after graduation' dollar value from page text.

    Returns an integer dollar amount or None if not found.
    """
    m = re.search(r"Median earnings 5 years after graduation[^$]*\$(\d[\d,]*)", text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None


def extract_faqs(soup: BeautifulSoup, limit: int = 3) -> list[dict]:
    """Extract a few FAQ question/answer pairs from the FAQPage JSON-LD, if present."""
    faqs: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            data = json.loads(raw)
        except Exception:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if not isinstance(obj, dict):
                continue
            if obj.get("@type") != "FAQPage":
                continue
            for q in obj.get("mainEntity", []):
                if not isinstance(q, dict) or q.get("@type") != "Question":
                    continue
                question = (q.get("name") or "").strip()
                ans_obj = q.get("acceptedAnswer")
                if isinstance(ans_obj, list):
                    ans_obj = ans_obj[0] if ans_obj else None
                answer = ""
                if isinstance(ans_obj, dict):
                    answer = (ans_obj.get("text") or "").strip()
                if question and answer:
                    faqs.append({"question": question, "answer": answer})
                    if len(faqs) >= limit:
                        return faqs
    return faqs


def score_to_label(score: float) -> str:
    if score <= -0.8:
        return "very conservative"
    if score <= -0.3:
        return "conservative"
    if score < 0.3:
        return "moderate / independent"
    if score < 0.8:
        return "liberal"
    return "very liberal"


def save_debug_html(slug: str, html: str):
    """Persist fetched HTML to scripts/niche_html/<slug>.html for debugging."""
    out_dir = ROOT / "scripts" / "niche_html"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.html"
    path.write_text(html, encoding="utf-8")

def save_next_data_json_from_html(slug: str, page_tag: str, html_str: str) -> None:
    """
    Best-effort helper to extract the __NEXT_DATA__ JSON from a Niche page
    and write it as pretty-printed JSON into the niche_html folder so we can
    debug tricky schools locally.

    Output path example:
      scripts/niche_html/{slug}_{page_tag}__next_data.json
    """
    try:
        m = re.search(
            r'id=[\'"]__NEXT_DATA__[\'"][^>]*>(.+?)</script>',
            html_str,
            flags=re.S | re.IGNORECASE,
        )
        if not m:
            return
        raw_json = m.group(1).strip()
        # __NEXT_DATA__ is HTML-escaped inside the script tag
        try:
            from html import unescape
            raw_json = unescape(raw_json)
        except Exception:
            pass
        data = json.loads(raw_json)
    except Exception:
        # Debug helper must never crash the main scraper
        return

    try:
        out_dir = ROOT / "scripts" / "niche_html"
    except NameError:
        out_dir = Path(__file__).resolve().parents[1] / "scripts" / "niche_html"

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slug}_{page_tag}__next_data.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        # Swallow any file I/O errors; this is debug-only
        return


def extract_politics_label(
    slug: str,
    headless: bool = True,
    proxy: Optional[str] = None,
    captcha_pause: bool = False,
    force_browser: bool = False,
) -> str:
    """
    Best-effort parse of politics distribution from Niche students page.
    Looks for label + percent pairs, computes weighted score.
    """
    url = f"https://www.niche.com/colleges/{slug}/students/"
    log(f"[POLITICS] fetch students page for {slug} (force_browser={force_browser})")
    log(f"[MAIN] fetch {url} (force_browser={force_browser})")
    html = fetch_html(url, force_browser=force_browser)
    if not html:
        log("[POLITICS] falling back to browser_fetch")
        html = browser_fetch(
            url,
            headless=headless,
            proxy=proxy,
            captcha_pause=captcha_pause,
            wait_selectors=[
                "text=Politics",
                "text=Very Conservative",
                "text=Balanced",
            ],
        )
    if html:
        log(f"[POLITICS] fetched {len(html)} bytes")
    if not html:
        cache_path = ROOT / "scripts" / "niche_html" / f"{slug}_students.html"
        if cache_path.exists():
            html = cache_path.read_text(encoding="utf-8")
    if html:
        save_debug_html(f"{slug}_students", html)
        # Save the embedded __NEXT_DATA__ JSON for the students route
        save_next_data_json_from_html(slug, "students", html)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True).lower()
    matches = re.findall(
        r"(very conservative|conservative|moderate|balanced|liberal|very liberal)\s*(\d+)%?",
        text,
        flags=re.IGNORECASE,
    )
    if not matches:
        cache_path = ROOT / "scripts" / "niche_html" / f"{slug}_students.html"
        if cache_path.exists():
            alt_html = cache_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(alt_html, "html.parser")
            text = soup.get_text(" ", strip=True).lower()
            matches = re.findall(
                r"(very conservative|conservative|moderate|balanced|liberal|very liberal)\s*(\d+)%?",
                text,
                flags=re.IGNORECASE,
            )
    if not matches:
        # try embedded __NEXT_DATA__ JSON for politics counts
        m = re.search(
            r'id=[\'"]__NEXT_DATA__[\'"][^>]*>(.+?)</script>',
            html,
            flags=re.S | re.IGNORECASE,
        )
        if not m and "alt_html" in locals():
            m = re.search(
                r'id=[\'"]__NEXT_DATA__[\'"][^>]*>(.+?)</script>',
                alt_html,
                flags=re.S | re.IGNORECASE,
            )
        if m:
            try:
                from html import unescape
                raw_json = unescape(m.group(1).strip())
                data = json.loads(raw_json)
            except Exception:
                data = None

            if data is not None:
                def normalize_key(k: str) -> str:
                    # lower-case and strip non-letters so e.g. "veryConservative"
                    # and "very_conservative" both become "veryconservative"
                    return re.sub(r"[^a-z]", "", k.lower())

                candidate = None

                def search(obj):
                    nonlocal candidate
                    if isinstance(obj, dict):
                        # build a normalized-key view
                        norm_map = {normalize_key(k): k for k in obj.keys()}
                        keys_present = set(norm_map.keys())

                        needed = {"veryconservative", "conservative", "moderate", "liberal", "veryliberal"}
                        if needed.issubset(keys_present):
                            # we found an object that has all the buckets we care about
                            cand = {}
                            for norm_label, out_label in [
                                ("veryconservative", "very conservative"),
                                ("conservative", "conservative"),
                                ("moderate", "moderate"),
                                ("liberal", "liberal"),
                                ("veryliberal", "very liberal"),
                            ]:
                                key = norm_map.get(norm_label)
                                if key is not None:
                                    try:
                                        val = obj[key]
                                        if isinstance(val, (int, float, str)):
                                            cand[out_label] = float(str(val))
                                    except Exception:
                                        continue
                            # balanced is optional
                            bal_key = norm_map.get("balanced")
                            if bal_key is not None:
                                try:
                                    val = obj[bal_key]
                                    if isinstance(val, (int, float, str)):
                                        cand["balanced"] = float(str(val))
                                except Exception:
                                    pass
                            if cand:
                                candidate = cand
                                return

                        for v in obj.values():
                            if candidate is not None:
                                return
                            search(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            if candidate is not None:
                                return
                            search(v)

                search(data)
                if candidate:
                    matches = [(k, str(v)) for k, v in candidate.items() if v is not None]
    if not matches:
        return ""

    total = 0
    score = 0.0
    for label, pct_str in matches:
        pct = float(pct_str)
        total += pct
        weight = POLITICS_WEIGHTS.get(label, 0.0)
        score += weight * pct
    if total == 0:
        return ""
    score = score / total
    return score_to_label(score)

def extract_diversity(
    slug: str,
    headless: bool = True,
    proxy: Optional[str] = None,
    captcha_pause: bool = False,
    force_browser: bool = False,
):
    """
    Extract racial diversity breakdown from the students page.
    Returns (breakdown_dict, diversity_index, diversity_label) or (None, None, None)
    Diversity index: Simpson's diversity index (1 - sum(p_i^2)).
    """
    url = f"https://www.niche.com/colleges/{slug}/students/"
    log(f"[DIVERSITY] fetch students page for {slug} (force_browser={force_browser})")
    html = fetch_html(url, force_browser=force_browser)
    if not html:
        log("[DIVERSITY] falling back to browser_fetch")
        html = browser_fetch(
            url,
            headless=headless,
            proxy=proxy,
            captcha_pause=captcha_pause,
            wait_selectors=[
                "text=Race",
                "text=Ethnicity",
                "text=White",
                "text=Hispanic",
            ],
        )
    if html:
        log(f"[DIVERSITY] fetched {len(html)} bytes")
    if not html:
        cache_path = ROOT / "scripts" / "niche_html" / f"{slug}_students.html"
        if cache_path.exists():
            html = cache_path.read_text(encoding="utf-8")
    if not html:
        return None, None, None

    groups = [
        "African American",
        "Black",
        "Asian",
        "Hispanic",
        "International",
        "Non-Citizen",
        "Multiracial",
        "Native American",
        "Pacific Islander",
        "Unknown",
        "White",
    ]
    pattern = r"(" + "|".join(groups) + r")\s*(\d+)%"
    matches = re.findall(pattern, html, flags=re.IGNORECASE)
    if not matches:
        # try text-stripped version
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
    if not matches:
        # try embedded __NEXT_DATA__ JSON for race/ethnicity breakdown
        m = re.search(
            r'id=[\'"]__NEXT_DATA__[\'"][^>]*>(.+?)</script>',
            html,
            flags=re.S | re.IGNORECASE,
        )
        if m:
            try:
                from html import unescape
                raw_json = unescape(m.group(1).strip())
                data = json.loads(raw_json)
            except Exception:
                data = None

            if data is not None:
                race_candidate = None

                def search(obj):
                    nonlocal race_candidate
                    if isinstance(obj, dict):
                        # look for an object that appears to be race counts/percentages
                        keys = [k.lower() for k in obj.keys()]
                        # require at least two common race keys to avoid false positives
                        race_keys = {"white", "black", "african", "hispanic", "asian", "international", "non-citizen"}
                        if len(race_keys.intersection(set(keys))) >= 2:
                            tmp = {}
                            for k, v in obj.items():
                                k_norm = k.lower()
                                try:
                                    val = float(str(v))
                                except Exception:
                                    continue
                                tmp[k_norm] = val
                            if tmp:
                                race_candidate = tmp
                                return
                        for v in obj.values():
                            if race_candidate is not None:
                                return
                            search(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            if race_candidate is not None:
                                return
                            search(v)

                search(data)
                if race_candidate:
                    matches = []
                    for k_norm, val in race_candidate.items():
                        # only keep sane 0–100 values
                        if not (0 <= val <= 100):
                            continue
                        label = k_norm
                        if "black" in label or "african" in label:
                            label = "African American"
                        elif "non-citizen" in label or "international" in label or "noncitizen" in label:
                            label = "International"
                        elif "white" in label:
                            label = "White"
                        elif "asian" in label:
                            label = "Asian"
                        elif "hispanic" in label or "latino" in label:
                            label = "Hispanic"
                        matches.append((label, str(val)))

    if not matches:
        return None, None, None

    breakdown = {}
    for label, pct in matches:
        norm_label = label.lower().strip()
        # unify similar labels
        if norm_label == "black":
            norm_label = "african american"
        if norm_label == "non-citizen":
            norm_label = "international"
        pct_val = float(pct)
        breakdown[norm_label] = pct_val

    total_pct = sum(breakdown.values())
    if total_pct <= 0:
        return breakdown, None, None

    # Normalize to proportions
    proportions = {k: v / total_pct for k, v in breakdown.items()}
    diversity_index = 1.0 - sum(p * p for p in proportions.values())

    if diversity_index >= 0.8:
        diversity_label = "Very diverse"
    elif diversity_index >= 0.7:
        diversity_label = "Diverse"
    elif diversity_index >= 0.6:
        diversity_label = "Moderately diverse"
    else:
        diversity_label = "Less diverse"

    return breakdown, round(diversity_index, 3), diversity_label


def update_team(team: dict, headless: bool = True, proxy: Optional[str] = None, captcha_pause: bool = False, force_browser: bool = False) -> bool | str:
    slug = team.get("niche_data_slug")
    if not slug:
        return False

    url = f"https://www.niche.com/colleges/{slug}/"
    html = fetch_html(url, force_browser=force_browser)
    if not html:
        html = fetch_html_playwright(url, headless=headless, proxy=proxy, captcha_pause=captcha_pause)
    if not html:
        html = fetch_html_undetected(url, headless=headless, proxy=proxy, captcha_pause=captcha_pause)
    if not html:
        cache_path = ROOT / "scripts" / "niche_html" / f"{slug}.html"
        if cache_path.exists():
            html = cache_path.read_text(encoding="utf-8")
    if html:
        save_debug_html(slug, html)
        # Also save the embedded __NEXT_DATA__ JSON for the main Niche page
        save_next_data_json_from_html(slug, "main", html)
    if not html:
        return "no_html"

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    niche = team.get("niche", {}) or {}
    before = niche.copy()

    niche["overall_grade"] = extract_overall_grade(soup) or niche.get("overall_grade", "")
    niche["academics_grade"] = extract_grade(text, "Academics") or niche.get("academics_grade", "")
    niche["value_grade"] = extract_grade(text, "Value") or niche.get("value_grade", "")
    niche["summary"] = extract_summary(soup) or niche.get("summary", "")

    pos, neg = extract_reviews(
        slug,
        headless=headless,
        proxy=proxy,
        captcha_pause=captcha_pause,
        force_browser=force_browser,
    )
    if pos:
        niche["review_pos"] = pos
    if neg:
        niche["review_neg"] = neg

    team["niche"] = niche

    # Enrich niche section with structured data from JSON-LD and meta tags
    jsonld_info = extract_jsonld_college_data(soup)
    for key in ("street", "city", "state", "zip_code", "phone", "website"):
        val = jsonld_info.get(key)
        if val:
            niche[key] = val

    # Aggregate rating: Niche star rating and review count
    rating_val = jsonld_info.get("rating_value")
    rating_cnt = jsonld_info.get("rating_count")
    if rating_val is not None:
        niche["rating_value"] = rating_val
    if rating_cnt is not None:
        niche["rating_count"] = rating_cnt

    # Latitude/longitude from meta tags (with JSON-LD as a fallback if it ever includes geo)
    latlon = extract_meta_lat_lon(soup)
    if jsonld_info.get("lat") is not None and "lat" not in latlon:
        latlon["lat"] = jsonld_info["lat"]
    if jsonld_info.get("lon") is not None and "lon" not in latlon:
        latlon["lon"] = jsonld_info["lon"]
    if latlon.get("lat") is not None:
        niche["lat"] = latlon["lat"]
    if latlon.get("lon") is not None:
        niche["lon"] = latlon["lon"]

    # Median earnings 5 years after graduation (if present in the page text)
    median_earn = extract_median_earnings_5y(text)
    if median_earn is not None:
        niche["median_earnings_5y"] = median_earn

    # A few high-level FAQ Q&A pairs about student life, campus vibe, etc.
    faqs = extract_faqs(soup, limit=3)
    if faqs:
        niche["faqs"] = faqs

    team["niche"] = niche

    # Update politics label (best effort; leave untouched if not found)
    politics_label = extract_politics_label(slug, headless=headless, proxy=proxy, captcha_pause=captcha_pause, force_browser=force_browser)
    if not politics_label:
        politics_label = extract_politics_label(slug, headless=headless, proxy=proxy, captcha_pause=captcha_pause, force_browser=force_browser)  # second try if first fetch cached None
    if politics_label:
        team["political_label"] = politics_label

    # Diversity
    diversity_breakdown, diversity_index, diversity_label = extract_diversity(slug, headless=headless, proxy=proxy, captcha_pause=captcha_pause, force_browser=force_browser)
    if diversity_breakdown:
        niche["diversity_breakdown"] = diversity_breakdown
    if diversity_index is not None:
        niche["diversity_index"] = diversity_index
    if diversity_label:
        niche["diversity_label"] = diversity_label

    return (niche != before) or bool(politics_label)


def main():
    parser = argparse.ArgumentParser(description="Update teams.json with Niche data using niche_data_slug.")
    parser.add_argument("--teams-json", type=Path, default=TEAMS_PATH, help="Path to settings/teams.json")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument("--verbose", action="store_true", help="Print per-team status")
    parser.add_argument("--team", action="append", dest="teams_filter", help="Only update specific team(s); can be used multiple times")
    parser.add_argument("--cookie", type=str, help="Cookie header to use for Niche requests (for bypassing bot protection)")
    parser.add_argument("--cookie-file", type=Path, help="Path to file containing Cookie header (takes precedence over --cookie)")
    parser.add_argument("--headful", action="store_true", help="Run Playwright non-headless (may help with bot checks)")
    parser.add_argument("--proxy", type=str, help="Optional proxy server for Playwright (e.g., http://host:port)")
    parser.add_argument("--html-only", action="store_true", help="Only fetch and save HTML to scripts/niche_html (no parsing/writes)")
    parser.add_argument("--no-skip", action="store_true", help="Process all teams even if niche summary/political_label already present")
    parser.add_argument("--captcha-pause", action="store_true", help="Pause after page load so you can solve a captcha manually, then press Enter")
    parser.add_argument("--force-browser", action="store_true", help="Skip direct HTTP fetch and force opening Playwright/undetected browser for every page")
    parser.add_argument("--prompt-next", action="store_true", help="Prompt before processing each school")
    parser.add_argument("--render-wait-ms", type=int, default=4000, help="Extra wait after page load to allow client rendering (ms)")
    args = parser.parse_args()

    global COOKIE_STR
    global FORCE_BROWSER
    global RENDER_WAIT_MS
    if args.cookie_file:
        if args.cookie_file.exists():
            COOKIE_STR = args.cookie_file.read_text().strip()
        else:
            parser.error(f"--cookie-file not found: {args.cookie_file}")
    elif args.cookie:
        COOKIE_STR = args.cookie
    elif "NICHE_COOKIE" in os.environ:
        COOKIE_STR = os.environ.get("NICHE_COOKIE")
    # If the user asks for headful, default to forcing browser fetches so pages actually open.
    FORCE_BROWSER = args.force_browser or args.headful
    RENDER_WAIT_MS = args.render_wait_ms

    teams = json.load(open(args.teams_json, "r", encoding="utf-8"))
    updated = 0
    skipped_existing = 0
    missing: list[str] = []

    targets = teams
    if args.teams_filter:
        wanted = set(args.teams_filter)
        targets = [t for t in teams if t.get("team") in wanted]

    for team in targets:
        name = team.get("team")
        slug = team.get("niche_data_slug")
        manual_selected = False

        if args.prompt_next:
            resp = input(f"Process {name}? [Y/n] ").strip().lower()
            if resp in ("n", "no"):
                if args.verbose:
                    print(f"[SKIP-MANUAL] {name}")
                continue
            manual_selected = True
        if args.html_only:
            if not slug:
                if args.verbose:
                    print(f"[SKIP] {name} (no slug)")
                continue
            url = f"https://www.niche.com/colleges/{slug}/"
            html = fetch_html(url, force_browser=FORCE_BROWSER)
            if not html:
                html = fetch_html_playwright(url, headless=not args.headful, proxy=args.proxy, captcha_pause=args.captcha_pause)
            if not html:
                html = fetch_html_undetected(url, headless=not args.headful, proxy=args.proxy, captcha_pause=args.captcha_pause)
            if html:
                save_debug_html(slug, html)
                if args.verbose:
                    print(f"[HTML SAVED] {name}")
            else:
                missing.append(name)
                if args.verbose:
                    print(f"[MISS] {name} (no HTML)")
        else:
            niche_obj = team.get("niche") or {}
            if (niche_obj.get("summary") and niche_obj.get("political_label")) and not (args.no_skip or manual_selected):
                skipped_existing += 1
                if args.verbose:
                    print(f"[SKIP] {name} (summary + political_label present)")
                time.sleep(args.delay)
                continue

            changed = update_team(team, headless=not args.headful, proxy=args.proxy, captcha_pause=args.captcha_pause, force_browser=FORCE_BROWSER)
            if changed == "no_html":
                missing.append(name)
                if args.verbose:
                    print(f"[MISS] {name} (no HTML)")
            elif changed:
                updated += 1
                if args.verbose:
                    print(f"[OK] {name}")
            else:
                if args.verbose:
                    print(f"[SKIP] {name}")
        time.sleep(args.delay)

    if args.html_only:
        print("HTML fetch complete.")
        if missing:
            print("No HTML fetched for:")
            for m in missing:
                print(f"  - {m}")
        return

    with open(args.teams_json, "w", encoding="utf-8") as f:
        json.dump(teams, f, indent=2)
        f.write("\n")

    print(f"Updated Niche data for {updated} team(s).")
    if skipped_existing:
        print(f"Skipped {skipped_existing} team(s) with existing overall_grade.")
    if missing:
        print("No Niche data fetched for:")
        for m in missing:
            print(f"  - {m}")

    # Close shared browser if it was opened
    close_browser()


if __name__ == "__main__":
    main()
