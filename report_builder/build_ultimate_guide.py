#!/usr/bin/env python3

import math
from pathlib import Path
import re
import json

import pandas as pd

# Local config loader
from .data_sources import (
    load_and_apply_config,
    load_player_settings,
    merge_overrides,
    load_schools_data,
    load_niche_data,
)
from .renderers.pdf_renderer import render_pdf


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

# These paths can be overridden by pipelines.build_pdf or guide.yml before calling main().
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent  # repo root
# Logos and assets now live inside report_builder/
LOGOS_DIR = ROOT_DIR / "report_builder" / "logos"
PNG_DIR = LOGOS_DIR
US_MAP_IMAGE = ROOT_DIR / "report_builder" / "assets" / "us_map_blank.png"
OUTPUT_PDF = ROOT_DIR / "report_builder" / "exports" / "Ultimate_School_Guide.pdf"
COACHES_CACHE_PATH = ROOT_DIR / "settings" / "coaches_cache.json"

# Data files (adjust paths if your CSVs live elsewhere)
TEAM_PIVOT_CSV = ROOT_DIR / "exports" / "team_pivot.csv"
ROSTERS_STATS_CSV = ROOT_DIR / "exports" / "rosters_and_stats.csv"
TRANSFERS_JSON = ROOT_DIR / "settings" / "transfers.json"

# If a school name in this script differs from the 'team' name in the CSVs,
# map it here so we can look it up correctly. Values are loaded from
# report_builder/config/guide.defaults.yml and may be overridden by guide.yml.
TEAM_NAME_ALIASES: dict[str, str] = {}

# Optional overrides for campus politics lean if provided manually
POLITICS_LABEL_OVERRIDES: dict[str, str] = {}

# Optional coach overrides: add or fill missing names/emails by team name
COACH_OVERRIDES: dict[str, list[dict[str, str]]] = {}

# Nearest major airport and high-level air travel notes (home-dependent text handled elsewhere)
AIRPORT_INFO: dict[str, dict[str, str]] = {}

# Per-school high-level risk / watchouts notes for the guide.
# These are intentionally brief and subjective, meant to flag things to monitor
# (roster competition, distance, system fit, etc.) rather than hard filters.
RISK_WATCHOUTS: dict[str, str] = {}

# Home base coordinates (default Indianapolis, IN). Overridden via player settings.
HOME_LAT = 39.7684
HOME_LON = -86.1581
PLAYER_SETTINGS_PATH = None
PLAYER = None
OUTPUT_PDF_WAS_OVERRIDDEN = False

# Academic tier → numeric score
TIER_POINTS = {
    "A": 3.0,
    "A-": 2.7,
    "B+": 2.3,
    "B": 2.0,
}

# Approximate lat/lon bounds for the contiguous US (for map plotting)
# Slightly expanded longitudes to better place east/west points on the map asset.
US_MIN_LAT = 24.0
US_MAX_LAT = 50.0
US_MIN_LON = -128.0
US_MAX_LON = -65.0

# -------------------------------------------------------------------
# CORE SCHOOL METADATA (HARDCODED LIST / ORDER)
# -------------------------------------------------------------------

# Optional: per-school normalized map coordinates for the static US map image.
# If provided, map_x/map_y should be floats in [0, 1] where:
#   x = 0 is the left edge of the contiguous US on the image,
#   x = 1 is the right edge of the contiguous US,
#   y = 0 is the bottom and y = 1 is the top.
# If map_x/map_y are absent, we fall back to lat/lon -> x/y projection.

SCHOOLS = load_schools_data()

# Seed defaults for logo map, politics, airport info, and aliases from teams.json
LOGO_MAP = {s["name"]: s.get("logo_map_name") for s in SCHOOLS if s.get("logo_map_name")}
POLITICS_LABEL_OVERRIDES = {s["name"]: s.get("political_label") for s in SCHOOLS if s.get("political_label")}
AIRPORT_INFO = {
    s["name"]: {
        "airport_name": s.get("airport_name", ""),
        "airport_code": s.get("airport_code", ""),
        "airport_drive_time": s.get("airport_drive_time", ""),
        "notes_from_indy": s.get("airport_notes", ""),
    }
    for s in SCHOOLS
    if s.get("airport_name") or s.get("airport_code")
}
TEAM_NAME_ALIASES = {s["name"]: s.get("team_name_aliases", [s["name"]])[0] for s in SCHOOLS}
RISK_WATCHOUTS = {s["name"]: s.get("risk_watchouts") for s in SCHOOLS if s.get("risk_watchouts")}


# -------------------------------------------------------------------
# LOGOS + NICHE-STYLE DATA
# -------------------------------------------------------------------

NICHE_DATA = load_niche_data()



# -------------------------------------------------------------------
# ENRICH DATA FROM CSV: TEAM PIVOT (RPI, RECORD, OFFENSE, VB OPP)
# -------------------------------------------------------------------

def filter_schools_for_player(player):
    """
    Restrict SCHOOLS to the player's interested list if provided.
    Mutates the global SCHOOLS list in place to keep downstream logic unchanged.
    """
    if not player or not getattr(player, "schools", None):
        return
    wanted = set(player.schools)
    filtered = [s for s in SCHOOLS if s["name"] in wanted]
    if filtered:
        SCHOOLS[:] = filtered

def enrich_schools_from_csv():
    """
    Override conference, offense_type, RPI rank, record, and VB opportunity score
    using real data from team_pivot.csv.

    Assumes team_pivot.csv has at least:
      - team
      - conference
      - offense_type
      - rank               (RPI)
      - projected_setter_count
      - record or overall_record (e.g. '20-11')

    If a school is not found, the original hard-coded values are preserved.
    """
    coaches_cache = load_coaches_cache()

    if not TEAM_PIVOT_CSV.exists():
        print(f"WARNING: team_pivot.csv not found at {TEAM_PIVOT_CSV}. "
              f"Using hard-coded values only.")
        return

    df = pd.read_csv(TEAM_PIVOT_CSV)
    if "team" not in df.columns:
        print("WARNING: team_pivot.csv is missing a 'team' column; "
              "cannot enrich school data.")
        return

    df["team"] = df["team"].astype(str)
    df = df.set_index("team")

    for s in SCHOOLS:
        school_name = s["name"]
        pivot_name = TEAM_NAME_ALIASES.get(school_name, school_name)
        s["politics_label"] = POLITICS_LABEL_OVERRIDES.get(school_name, "")

        if pivot_name not in df.index:
            print(f"WARNING: '{pivot_name}' not found in team_pivot.csv; "
                  f"leaving hard-coded values for {school_name}.")
            continue

        row = df.loc[pivot_name]

        def _clean(val):
            if pd.isna(val):
                return ""
            return str(val).strip()

        # Conference and offense type from pivot
        if "conference" in row:
            s["conference"] = str(row["conference"])
        if "offense_type" in row:
            s["offense_type"] = str(row["offense_type"])

        # RPI rank (if present)
        if "rank" in row:
            try:
                s["rpi_rank"] = float(row["rank"])
            except (TypeError, ValueError):
                s["rpi_rank"] = None

        # Record string (overall record), if present
        record_val = None
        if "record" in row:
            record_val = row["record"]
        elif "overall_record" in row:
            record_val = row["overall_record"]
        if isinstance(record_val, float) and math.isnan(record_val):
            record_val = None
        s["record"] = str(record_val) if record_val is not None else "N/A"

        # Compute VB opportunity score from projected_setter_count
        proj = None
        if "projected_setter_count" in row:
            proj = row["projected_setter_count"]
        try:
            proj = float(proj)
        except (TypeError, ValueError):
            proj = None

        # Base opportunity score: fewer effective setters = higher score
        if proj is None:
            base = s.get("vb_opp_score", 2.5)  # fall back to existing
        elif proj <= 1:
            base = 3.0
        elif proj <= 2:
            base = 2.7
        elif proj <= 3:
            base = 2.3
        else:
            base = 2.0

        offense = str(s.get("offense_type", "")).strip()
        # Slight penalty if running a 6-2 with multiple setters
        if offense == "6-2" and proj is not None and proj >= 2:
            base -= 0.2

        # Clamp and assign
        s["vb_opp_score"] = max(2.0, min(3.0, base))

        # Coaches: pull from overrides, then cache, then pivot row
        coaches: list[dict[str, str]] = []

        def add_or_update_coach(name: str, raw_title: str, email: str, phone: str = ""):
            if not name and not email and not raw_title and not phone:
                return
            title_lower = raw_title.lower()
            if "associate" in title_lower:
                title = "Associate Head Coach"
            elif "assistant" in title_lower:
                title = "Assistant Head Coach"
            elif "head" in title_lower:
                title = "Head Coach"
            else:
                title = raw_title

            email_norm = email.strip()
            phone_norm = normalize_phone(phone)

            # Check existing by name+title (case-insensitive)
            for c in coaches:
                if c["name"].strip().lower() == name.strip().lower() and c["title"].strip().lower() == title.strip().lower():
                    # If existing lacks email/phone and new has it, update
                    if email_norm and not c.get("email"):
                        c["email"] = email_norm
                    if phone_norm and not c.get("phone"):
                        c["phone"] = phone_norm
                    return

            coaches.append({"name": name, "title": title, "email": email_norm, "phone": phone_norm})

        # Overrides first
        if school_name in COACH_OVERRIDES:
            for c in COACH_OVERRIDES[school_name]:
                add_or_update_coach(c.get("name", ""), c.get("title", ""), c.get("email", ""), c.get("phone", ""))

        # Cache next
        cache_entry = coaches_cache.get(pivot_name) or coaches_cache.get(school_name)
        if cache_entry and isinstance(cache_entry, dict):
            cache_coaches = cache_entry.get("coaches", [])
            for c in cache_coaches:
                add_or_update_coach(c.get("name", ""), c.get("title", ""), c.get("email", ""), c.get("phone", ""))

        # Pivot row last
        for i in range(1, 6):
            add_or_update_coach(
                _clean(row.get(f"coach{i}_name", "")),
                _clean(row.get(f"coach{i}_title", "")),
                _clean(row.get(f"coach{i}_email", "")),
                _clean(row.get(f"coach{i}_phone", "")),
            )

        s["coaches"] = coaches

        # Politics label (from overrides or team_pivot column if present)
        if not s["politics_label"] and "politics_label" in df.columns:
            raw_pol = _clean(row.get("politics_label", ""))
            s["politics_label"] = normalize_politics_label(raw_pol)


# -------------------------------------------------------------------
# ENRICH DATA FROM CSV: ROSTERS & STATS (PROJECTED 2026 ROSTER)
# -------------------------------------------------------------------

def _first_existing_column(df: pd.DataFrame, candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_stat_value(val):
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except Exception:
        pass
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return f"{f:.1f}"
    except (TypeError, ValueError):
        return str(val)


def _get_column_case_insensitive(df: pd.DataFrame, candidates) -> str | None:
    """Return the first matching column name (case-insensitive) from candidates."""
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        real = lower_map.get(cand.lower())
        if real:
            return real
    return None


def _is_graduating_class(cls_val: str) -> bool:
    """Heuristic: treat Sr/Graduate variants as graduating this year."""
    if not cls_val:
        return False
    text = str(cls_val).lower().strip()
    if text.startswith("gr"):
        return True
    tokens = ["sr", "senior", "grad", "graduate", "gr.", "gr ", "gs"]
    return any(token in text for token in tokens)


def _parse_incoming_list(raw: str, default_pos: str) -> list[dict[str, str]]:
    """Parse comma-separated incoming names; keep optional position hints."""
    if not raw or (isinstance(raw, float) and pd.isna(raw)):
        return []
    entries = []
    for part in str(raw).split(","):
        name = part.strip()
        if not name:
            continue
        # Strip any inline position text; use provided default pos separately
        pos = default_pos
        if "(" in name and ")" in name:
            base = name.split("(")[0].strip()
        else:
            base = name
        entries.append({"name": base, "position": pos})
    return entries


def _advance_class(cls_val: str) -> str:
    """
    Advance class by one year for next-season projection.
    Examples:
        Fr -> So, So -> Jr, Jr -> Sr, Sr/Gr -> Graduated
        R-Fr -> R-So, R-So -> R-Jr, R-Jr -> R-Sr, R-Sr -> Graduated
    """
    if not cls_val:
        return ""
    text = str(cls_val).strip().lower()

    def base_next(base: str) -> str:
        if base in ("fr", "freshman"):
            return "So"
        if base in ("so", "soph", "sophomore"):
            return "Jr"
        if base in ("jr", "junior"):
            return "Sr"
        if base in ("sr", "senior", "gr", "gs", "grad", "graduate"):
            return "Graduated"
        return cls_val

    # Redshirt prefix handling
    rs_prefixes = ("r-", "r ", "rs-", "rs ")
    if any(text.startswith(pref) for pref in rs_prefixes):
        base = text.split("-", 1)[-1] if "-" in text else text.split(" ", 1)[-1]
        nxt = base_next(base)
        if nxt == "Graduated":
            return "Graduated"
        return f"R-{nxt}"

    return base_next(text)


def load_coaches_cache() -> dict[str, dict]:
    """Load cached coaches from JSON; returns mapping of team -> dict."""
    try:
        if not COACHES_CACHE_PATH.exists():
            return {}
        import json
        data = json.loads(COACHES_CACHE_PATH.read_text())
        return data.get("teams", {})
    except Exception:
        return {}


def normalize_phone(raw: str) -> str:
    """Format phone as (XXX) XXX-XXXX when possible."""
    if not raw:
        return ""
    import re
    digits = re.sub(r"\\D", "", str(raw))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    if len(digits) == 0:
        return ""
    return str(raw).strip()


def normalize_politics_label(raw: str) -> str:
    """
    Normalize free-text politics descriptions to a small set.
    Returns one of: Very conservative, Conservative, Moderate / independent,
    Liberal, Very liberal.
    """
    if not raw:
        return ""
    text = raw.strip().lower()
    if "very liberal" in text:
        return "Very liberal"
    if "liberal" in text:
        return "Liberal"
    if "very conservative" in text:
        return "Very conservative"
    if "conservative" in text:
        return "Conservative"
    if "moderate" in text or "independent" in text:
        return "Moderate / independent"
    return raw.strip()

def enrich_rosters_from_csv():
    """
    Attach a projected 2026 roster list to each school in SCHOOLS.

    Looks in rosters_and_stats.csv for:
        - team
        - player/name
        - class
        - height
        - kills
        - assists
        - digs
        - optional: on_2026_roster / include_2026 / is_2026_roster...

    Result:
        Each school dict gets s["roster_2026"] = [
            {"name", "class", "height", "kills", "assists", "digs"}, ...
        ]
    """
    pivot_df = None
    if TEAM_PIVOT_CSV.exists():
        pivot_df = pd.read_csv(TEAM_PIVOT_CSV)
        if "team" in pivot_df.columns:
            pivot_df["team"] = pivot_df["team"].astype(str)
            pivot_df = pivot_df.set_index("team")
        else:
            pivot_df = None

    if not ROSTERS_STATS_CSV.exists():
        print(f"WARNING: rosters_and_stats.csv not found at {ROSTERS_STATS_CSV}. "
              f"Skipping roster table enrichment.")
        return

    df = pd.read_csv(ROSTERS_STATS_CSV)

    transfers = []
    if TRANSFERS_JSON.exists():
        try:
            transfers = json.load(open(TRANSFERS_JSON, "r", encoding="utf-8"))
        except Exception:
            transfers = []

    def _norm_school(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

    def _norm_name(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

    team_col = _get_column_case_insensitive(df, ["team"])
    if not team_col:
        print("WARNING: rosters_and_stats.csv is missing a 'team' column; "
              "cannot attach rosters.")
        return

    name_col = _get_column_case_insensitive(df, ["name", "player", "player_name"])
    if not name_col:
        print("WARNING: rosters_and_stats.csv is missing a player/name column; "
              "cannot attach rosters.")
        return
    class_col = _get_column_case_insensitive(df, ["class_2026", "class_2025", "class", "eligibility", "year"])
    position_col = _get_column_case_insensitive(df, ["position", "pos"])
    height_col = _get_column_case_insensitive(df, ["height_safe", "height", "height_display"])
    kills_col = _get_column_case_insensitive(df, ["kills", "k"])
    assists_col = _get_column_case_insensitive(df, ["assists", "a"])
    digs_col = _get_column_case_insensitive(df, ["digs", "d"])

    include_col = _get_column_case_insensitive(
        df,
        [
            "on_2026_roster",
            "include_2026",
            "is_2026_roster",
            "is_on_2026_roster",
            "will_be_on_2026_roster",
        ],
    )

    df[team_col] = df[team_col].astype(str)

    for s in SCHOOLS:
        school_name = s["name"]
        pivot_name = TEAM_NAME_ALIASES.get(school_name, school_name)

        rows = df[df[team_col] == pivot_name].copy()
        outgoing_names = {
            _norm_name(x["name"])
            for x in transfers
            if _norm_school(x.get("old_team", "")) == _norm_school(pivot_name)
        }
        players = []
        seen_names = set()

        if not rows.empty:
            # If we have a column that explicitly flags 2026 roster, filter on that
            if include_col and include_col in rows.columns:
                flags = rows[include_col].astype(str).str.lower()
                mask = flags.isin(["1", "true", "yes", "y"])
                filtered = rows[mask]
                if not filtered.empty:
                    rows = filtered

            # Drop graduating classes (Sr/Grad)
            if class_col:
                rows = rows[~rows[class_col].astype(str).apply(_is_graduating_class)]

            for _, row in rows.iterrows():
                name = row[name_col] if name_col else None
                if name is None or (isinstance(name, float) and pd.isna(name)):
                    continue

                name_str = str(name).strip()
                name_key = name_str.lower()
                if _norm_name(name_str) in outgoing_names:
                    continue
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                cls = row[class_col] if class_col in row else None if class_col else None
                pos = row[position_col] if position_col in row else None if position_col else None
                height = row[height_col] if height_col in row else None if height_col else None
                kills = row[kills_col] if kills_col in row else None if kills_col else None
                assists = row[assists_col] if assists_col in row else None if assists_col else None
                digs = row[digs_col] if digs_col in row else None if digs_col else None
                next_cls = _advance_class(cls) if cls is not None else ""

                players.append(
                    {
                        "name": name_str,
                        "class": next_cls if next_cls else (str(cls) if cls is not None and not pd.isna(cls) else ""),
                        "position": str(pos) if pos is not None and not pd.isna(pos) else "",
                        "height": str(height) if height is not None and not pd.isna(height) else "",
                        "kills": _safe_stat_value(kills),
                        "assists": _safe_stat_value(assists),
                        "digs": _safe_stat_value(digs),
                    }
                )

        # Add incoming players from pivot (if present)
        if pivot_df is not None and pivot_name in pivot_df.index:
            prow = pivot_df.loc[pivot_name]
            incoming_fields = [
                ("incoming_setter_names", "S"),
                ("incoming_pin_names", "OH/RS"),
                ("incoming_middle_names", "MB"),
                ("incoming_def_names", "DS/L"),
            ]
            for col, pos_label in incoming_fields:
                if col in pivot_df.columns:
                    for inc in _parse_incoming_list(prow.get(col, ""), pos_label):
                        name_str = inc["name"]
                        name_key = name_str.lower()
                        if name_key in seen_names:
                            continue
                        seen_names.add(name_key)
                        players.append(
                            {
                                "name": name_str,
                                "class": "Fr",
                                "height": "",
                                "kills": "",
                                "assists": "",
                                "digs": "",
                                "position": inc.get("position", pos_label),
                            }
                        )

        s["roster_2026"] = players
        # Compute position-based VB opportunity score dynamically
        s["vb_opp_score"] = compute_vb_opportunity_score(players, getattr(PLAYER, "position", None))


# -------------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------------

def ensure_logos_unzipped():
    """Verify PNG logos folder exists and mapped files are present."""
    if not PNG_DIR.exists():
        raise FileNotFoundError(f"Could not find folder {PNG_DIR}")

    files = {p.name for p in PNG_DIR.iterdir() if p.is_file()}
    missing = [fname for fname in LOGO_MAP.values() if fname not in files]
    if missing:
        print("WARNING: These mapped filenames were not found in the folder:")
        for m in missing:
            print("  -", m)
    else:
        print("All mapped logo files found.")


def _exp_weight(cls: str) -> float:
    cls = (cls or "").lower()
    if cls.startswith("gr"):
        return 1.0
    if cls.startswith("sr"):
        return 0.9
    if cls.startswith("jr"):
        return 0.7
    if cls.startswith("so"):
        return 0.5
    if cls.startswith("fr"):
        return 0.3
    return 0.5


def _parse_minutes(text: str) -> float:
    """
    Parse a minutes string like '15 minutes', '15-20 min', or '15–20' into a single numeric value.
    Falls back to 0 if nothing is parseable.
    """
    if not text:
        return 0.0
    clean = text.replace("–", "-")
    nums = re.findall(r"\d+(?:[.,]\d+)?", clean)
    if not nums:
        return 0.0
    vals = [float(n.replace(",", ".")) for n in nums]
    if "-" in clean and len(vals) >= 2:
        return sum(vals[:2]) / 2.0  # average of the range
    return vals[0]


def _airport_codes(info: dict) -> set[str]:
    """
    Extract IATA-like codes from the airport_code field (handles 'ATL', 'ORD / MDW', etc.).
    """
    codes = set()
    text = info.get("airport_code", "") or ""
    for code in re.findall(r"[A-Z]{3}", text.upper()):
        codes.add(code)
    return codes


def _position_keys(text: str) -> set[str]:
    """
    Normalize a position string into canonical keys so that abbreviations
    (e.g., 'S') match full names (e.g., 'Setter').
    """
    canon_map = {
        "s": {"s", "set", "setter"},
        "pin": {"oh", "rs", "opp", "opposite", "outside", "pin"},
        "mb": {"mb", "mh", "middle"},
        "def": {"ds", "l", "lib", "libero", "def"},
    }

    tokens = {tok for tok in re.split(r"[^a-zA-Z]+", (text or "").lower()) if tok}
    keys: set[str] = set()

    for tok in tokens:
        matched = False
        for canon, variants in canon_map.items():
            if tok in variants:
                keys.add(canon)
                matched = True
                break
        if not matched:
            keys.add(tok)

    return keys


def compute_vb_opportunity_score(roster, player_position: str | None):
    """
    Heuristic: fewer experienced players at the same position => higher opportunity.
    Returns score on a 1.0–3.0 scale (3 = best opportunity).
    """
    if not player_position:
        return 2.0  # neutral if we don't know the position

    player_keys = _position_keys(player_position)
    if not player_keys:
        return 2.0

    same_pos = []
    for p in roster:
        if player_keys & _position_keys(p.get("position", "")):
            same_pos.append(p)

    if not same_pos:
        return 3.0

    exp_load = sum(_exp_weight(p.get("class", "")) for p in same_pos)
    score = max(1.0, min(3.0, 3.0 - 0.4 * exp_load))
    return round(score, 2)


def auto_risk_watchouts(s: dict, player_position: str | None) -> str:
    """Auto-generate a short 'Risk / Watchouts' blurb based on
    conference, distance, travel difficulty, and vb_opp_score.
    """
    msgs: list[str] = []

    conf = (s.get("conference") or "").strip()
    tier = (s.get("tier") or "").strip()
    drive = float(s.get("drive_dist_mi") or 0)
    travel_diff = int(s.get("travel_difficulty") or 0)
    vb_opp = float(s.get("vb_opp_score") or 2.0)

    # Example heuristics – tweak as you like:
    power_confs = {"Big 12", "ACC", "Big East", "Big Ten", "SEC", "Pac-12"}

    if conf in power_confs:
        msgs.append(
            "Power-conference competition; playing time may depend on winning a role early."
        )

    if vb_opp <= 2.2:
        msgs.append(
            "Setter room may be crowded; monitor depth chart and portal additions closely."
        )
    elif vb_opp >= 2.9:
        msgs.append(
            "High current opportunity, but staff may bring in more setters quickly."
        )

    if drive > 800 or travel_diff >= 60:
        msgs.append("Long-distance travel and separation from home are non-trivial factors.")

    if tier in ("A", "A-"):
        msgs.append("Stronger academic profile may come with higher workload and expectations.")

    if not msgs:
        msgs.append(
            "No major structural risks flagged; focus on staff fit, culture, and major alignment."
        )

    return " ".join(msgs)


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in miles."""
    R_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_km = R_km * c
    return dist_km * 0.621371


def compute_travel_and_fit():
    """
    For each school in SCHOOLS, compute:
    - drive_dist_mi (approx)
    - drive_time_hr
    - flight_dist_mi
    - flight_time_hr
    - travel_difficulty (0–100)
    - academic_score
    - fit_score
    """
    for s in SCHOOLS:
        # Distance
        if s.get("lat") is None or s.get("lon") is None:
            # Skip travel computations if coordinates are missing
            s["flight_dist_mi"] = s["drive_dist_mi"] = s["drive_time_hr"] = s["flight_time_hr"] = 0
            s["travel_difficulty"] = 10
            s["geo_score"] = 1.5
            continue
        d_miles = haversine_miles(HOME_LAT, HOME_LON, s["lat"], s["lon"])
        s["flight_dist_mi"] = round(d_miles, 1)
        s["drive_dist_mi"] = round(d_miles * 1.15, 1)  # fudge factor for roads

        # Times
        s["drive_time_hr"] = round(s["drive_dist_mi"] / 60.0, 1)  # assume 60 mph avg
        s["flight_time_hr"] = round(s["flight_dist_mi"] / 450.0, 2)  # assume 450 mph avg jet

        # Travel difficulty: branch by likely mode (short drives vs flights)
        DRIVE_ONLY_THRESHOLD = 350  # miles; below this we assume you'd just drive
        info = AIRPORT_INFO.get(s["name"], {})
        notes = (info.get("notes_from_indy") or "").lower()
        has_direct = bool(re.search(r"\bnon[- ]?stop\b|\bdirect\b", notes))
        has_multi_stop = bool(re.search(r"\b2[- ]?stop|\btwo[- ]?stop|\bmulti[- ]?stop", notes))

        drive_minutes_airport = _parse_minutes(info.get("airport_drive_time", ""))
        congestion_codes = {"ATL", "ORD", "LAX", "JFK", "EWR", "DFW", "DEN", "SFO", "CLT", "IAH", "PHX", "BOS", "LGA"}
        codes_here = _airport_codes(info)
        congestion_penalty = 8 if codes_here & congestion_codes else 0

        if s["drive_dist_mi"] <= DRIVE_ONLY_THRESHOLD:
            # Driving scenario: lighter base, no airport overhead
            base = s["drive_dist_mi"] / 18.0  # scale so nearby trips stay low, longer drives rise meaningfully
            base += 6  # small fatigue/parking penalty
        else:
            # Flying scenario: add airport overhead, distance, and congestion
            base = s["flight_dist_mi"] / 18.0
            base += drive_minutes_airport / 3.0  # first/last mile to campus
            base += 20  # airport process (arrive early, parking, baggage/rental)
            if has_direct:
                base -= 10
            elif has_multi_stop:
                base += 10
            base += congestion_penalty
            # Long-haul bump
            if s["flight_dist_mi"] > 1600:
                base += 5

        s["travel_difficulty"] = int(min(100, max(10, base)))

        # Geo score (higher is better proximity) derived from drive distance
        if s["drive_dist_mi"] <= 300:
            s["geo_score"] = 3.0
        elif s["drive_dist_mi"] <= 600:
            s["geo_score"] = 2.5
        elif s["drive_dist_mi"] <= 1000:
            s["geo_score"] = 2.0
        elif s["drive_dist_mi"] <= 1500:
            s["geo_score"] = 1.5
        else:
            s["geo_score"] = 1.0

        # Academic score
        tier = s["tier"]
        s["academic_score"] = TIER_POINTS.get(tier, 2.0)

        # Fit score:
        # Fit = (academics * 0.4) + (vb_opp_score * 0.4) + (geo_score * 0.2)
        s["fit_score"] = round(
            s["academic_score"] * 0.4 +
            s["vb_opp_score"] * 0.4 +
            s["geo_score"] * 0.2,
            2
        )

        # Auto-fill risk/watchouts if not already provided in SCHOOLS
        if not s.get("risk_watchouts"):
            s["risk_watchouts"] = auto_risk_watchouts(s, getattr(PLAYER, "position", None))
    


# -------------------------------------------------------------------
# PDF BUILDING
# -------------------------------------------------------------------


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------


# -------------------------------------------------------------------

def main():
    # Apply YAML config overrides (paths + data) before doing any work
    import sys
    load_and_apply_config(module=sys.modules[__name__])

    # Load player settings and filter schools/home base
    global PLAYER, HOME_LAT, HOME_LON, OUTPUT_PDF
    PLAYER = load_player_settings(Path(PLAYER_SETTINGS_PATH) if PLAYER_SETTINGS_PATH else None)
    if getattr(PLAYER, "home_lat", None) and getattr(PLAYER, "home_lon", None):
        HOME_LAT = float(PLAYER.home_lat)
        HOME_LON = float(PLAYER.home_lon)
    # Apply per-player shallow overrides
    if getattr(PLAYER, "risk_watchouts", None):
        merge_overrides(RISK_WATCHOUTS, PLAYER.risk_watchouts)
    if getattr(PLAYER, "airport_info", None):
        merge_overrides(AIRPORT_INFO, PLAYER.airport_info)
    if getattr(PLAYER, "politics_label_overrides", None):
        merge_overrides(POLITICS_LABEL_OVERRIDES, PLAYER.politics_label_overrides)
    if getattr(PLAYER, "team_name_aliases", None):
        merge_overrides(TEAM_NAME_ALIASES, PLAYER.team_name_aliases)
    filter_schools_for_player(PLAYER)

    # If output path wasn't explicitly overridden, personalize filename
    if not OUTPUT_PDF_WAS_OVERRIDDEN:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", getattr(PLAYER, "name", "Player")).strip("_") or "Player"
        OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
        new_name = f"Ultimate_School_Guide_{slug}.pdf"
        OUTPUT_PDF = OUTPUT_PDF.with_name(new_name)

    ensure_logos_unzipped()
    enrich_schools_from_csv()
    enrich_rosters_from_csv()
    compute_travel_and_fit()
    render_pdf(core_module=sys.modules[__name__])
    print(f"\nUltimate guide written to: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
