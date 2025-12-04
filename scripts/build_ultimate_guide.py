#!/usr/bin/env python3
"""
build_ultimate_guide.py

Builds a fully branded "Ultimate Guide" PDF for Molly's transfer process.

What it does:
- Reads logos from vb_scraper/logos (PNG files already extracted)
- Uses a hard-coded data model for 23 target schools:
    * Name, city/state, conference
    * Academic tier
    * Offense type (5-1 / 6-2, defaulted and then overridden from team_pivot)
    * Location (lat/lon)
    * Volleyball opportunity score (overridden from pivot)
    * Geography score (desirability/fit)
- Reads real data from:
    * team_pivot.csv  (RPI rank, conference, offense type, projected setter count, record)
    * rosters_and_stats.csv (projected 2026 roster + stats)
- Computes:
    * Great-circle distance from Indianapolis, IN
    * Approximate driving distance & time
    * Approximate flight distance & time
    * Travel Difficulty Score
    * Overall Fit Score (academics x VB opportunity x geography)
- Renders:
    * Cover page with 5-column logo grid
    * Fit Score ranking table (with RPI)
    * Travel distance matrix
    * School-by-school pages including:
        - Logo & basic profile
        - RPI & record
        - Niche-style grades, summary & reviews
        - Travel info
        - Program & fit notes
        - Projected 2026 roster table (Name, Class, Height, Kills, Assists, Digs)

Requirements:
    pip install reportlab pandas
"""

import math
from pathlib import Path
import re

import pandas as pd
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from xml.sax.saxutils import escape


# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
LOGOS_DIR = ROOT_DIR / "logos"
# Logos live directly under vb_scraper/logos
PNG_DIR = LOGOS_DIR
US_MAP_IMAGE = ROOT_DIR / "assets" / "us_map_blank.png"
OUTPUT_PDF = ROOT_DIR / "exports" / "Ultimate_School_Guide_FULL_LOCAL.pdf"
COACHES_CACHE_PATH = ROOT_DIR / "settings" / "coaches_cache.json"

# Data files (adjust paths if your CSVs live elsewhere)
TEAM_PIVOT_CSV = ROOT_DIR / "exports" / "team_pivot.csv"
ROSTERS_STATS_CSV = ROOT_DIR / "exports" / "rosters_and_stats.csv"

# If a school name in this script differs from the 'team' name in the CSVs,
# map it here so we can look it up correctly.
TEAM_NAME_ALIASES = {
    "University of Connecticut (UConn)": "University of Connecticut",
    "North Carolina State University (NC State)": "North Carolina State University",
    "University of North Carolina at Charlotte (Charlotte)": "University of North Carolina at Charlotte",
    "Virginia Commonwealth University (VCU)": "Virginia Commonwealth University",
    "Northern Arizona University (NAU)": "Northern Arizona University",
    "University of Maryland, Baltimore County (UMBC)": "University of Maryland, Baltimore County",
}

# Optional overrides for campus politics lean if provided manually
POLITICS_LABEL_OVERRIDES: dict[str, str] = {
    "Iowa State University": "Moderate / independent",
    "Kansas State University": "Conservative",
    "University of Utah": "Moderate / independent",
    "Florida State University": "Moderate / independent",
    "Drake University": "Moderate / independent",
    "Florida Gulf Coast University": "Moderate / independent",
    "University of Connecticut (UConn)": "Liberal",
    "Boise State University": "Moderate / independent",
    "Morehead State University": "Conservative",
    "University of Toledo": "Moderate / independent",
    "University of Northern Colorado": "Moderate / independent",
    "University of South Alabama": "Conservative",
    "University of Illinois Chicago (UIC)": "Liberal",
    "Loyola University Chicago": "Liberal",
    "North Carolina State University (NC State)": "Moderate / independent",
    "University of North Carolina at Charlotte (Charlotte)": "Moderate / independent",
    "Virginia Commonwealth University (VCU)": "Liberal",
    "Georgia Southern University": "Conservative",
    "Northern Arizona University (NAU)": "Moderate / independent",
    "Georgia State University": "Liberal",
    "University of Denver": "Liberal",
    "Valparaiso University": "Moderate / independent",
    "University of Maryland, Baltimore County (UMBC)": "Liberal",
}

# Optional coach overrides: add or fill missing names/emails by team name
# Example:
# COACH_OVERRIDES = {
#     "Kansas State University": [
#         {"name": "Jason Mansfield", "title": "Head Coach", "email": "jmansfield@k-state.edu"},
#     ],
# }

COACH_OVERRIDES: dict[str, list[dict[str, str]]] = {
    "Kansas State University": [
         {"name": "Jason Mansfield", "title": "Head Coach", "email": "jmansfield@k-state.edu"},
     ],
}

# Nearest major airport and high-level air travel notes from Indianapolis (IND).
# This is intentionally approximate; routes change, so always check current schedules.
AIRPORT_INFO: dict[str, dict[str, str]] = {
    "Iowa State University": {
        "airport_name": "Des Moines International Airport",
        "airport_code": "DSM",
        "airport_drive_time": "40 minutes",
        "notes_from_indy": (
            "Typically reached via one-stop routes from Indianapolis (IND), "
            "usually connecting through hubs such as Chicago (ORD) or Denver (DEN)."
        ),
    },
    "Kansas State University": {
        "airport_name": "Manhattan Regional Airport (alt: Kansas City International)",
        "airport_code": "MHK / MCI",
        "airport_drive_time": "15–20 minutes to MHK (about 2 hours to MCI)",
        "notes_from_indy": (
            "Most itineraries from IND connect once, often via Chicago (ORD) or Dallas–Fort Worth (DFW), "
            "into Manhattan (MHK) or Kansas City (MCI)."
        ),
    },
    "University of Utah": {
        "airport_name": "Salt Lake City International Airport",
        "airport_code": "SLC",
        "airport_drive_time": "15 minutes",
        "notes_from_indy": (
            "Usually served from IND with one-stop service via major hubs like Denver (DEN), Dallas–Fort Worth (DFW), or Chicago (ORD)."
        ),
    },
    "Florida State University": {
        "airport_name": "Tallahassee International Airport",
        "airport_code": "TLH",
        "airport_drive_time": "15–20 minutes",
        "notes_from_indy": (
            "Commonly reached via one-stop routes from IND through Atlanta (ATL) or Charlotte (CLT)."
        ),
    },
    "Drake University": {
        "airport_name": "Des Moines International Airport",
        "airport_code": "DSM",
        "airport_drive_time": "10–15 minutes",
        "notes_from_indy": (
            "Typically a one-stop trip from IND, often connecting through Chicago (ORD)."
        ),
    },
    "Florida Gulf Coast University": {
        "airport_name": "Southwest Florida International Airport",
        "airport_code": "RSW",
        "airport_drive_time": "15–20 minutes",
        "notes_from_indy": (
            "Most flights from IND involve one connection, commonly via Atlanta (ATL) or Charlotte (CLT)."
        ),
    },
    "University of Connecticut (UConn)": {
        "airport_name": "Bradley International Airport",
        "airport_code": "BDL",
        "airport_drive_time": "35–40 minutes",
        "notes_from_indy": (
            "Usually reached with one stop from IND, often via Chicago (ORD) or Washington (IAD/DCA)."
        ),
    },
    "Boise State University": {
        "airport_name": "Boise Airport",
        "airport_code": "BOI",
        "airport_drive_time": "10 minutes",
        "notes_from_indy": (
            "Generally a one-stop trip from IND, commonly connecting through Denver (DEN), Salt Lake City (SLC), or another western hub."
        ),
    },
    "Morehead State University": {
        "airport_name": "Blue Grass Airport (Lexington)",
        "airport_code": "LEX",
        "airport_drive_time": "~1 hour",
        "notes_from_indy": (
            "Drivable from Indianapolis; when flying, typical one-stop routes use hubs like Charlotte (CLT) or Chicago (ORD) into LEX."
        ),
    },
    "University of Toledo": {
        "airport_name": "Toledo Express Airport (alt: Detroit Metropolitan)",
        "airport_code": "TOL / DTW",
        "airport_drive_time": "25 minutes to TOL (about 55 minutes to DTW)",
        "notes_from_indy": (
            "Often a one-stop connection from IND via hubs like Chicago (ORD); some travelers also use Detroit (DTW) and drive."
        ),
    },
    "University of Northern Colorado": {
        "airport_name": "Denver International Airport",
        "airport_code": "DEN",
        "airport_drive_time": "50–60 minutes",
        "notes_from_indy": (
            "Commonly served from IND with either non-stop or one-stop options into Denver (DEN), then a drive to Greeley."
        ),
    },
    "University of South Alabama": {
        "airport_name": "Mobile Regional Airport (alt: Pensacola International)",
        "airport_code": "MOB / PNS",
        "airport_drive_time": "20–25 minutes",
        "notes_from_indy": (
            "Typical itineraries from IND connect once, often via Atlanta (ATL) into Mobile (MOB) or nearby Pensacola (PNS)."
        ),
    },
    "University of Illinois Chicago (UIC)": {
        "airport_name": "Chicago O'Hare / Midway",
        "airport_code": "ORD / MDW",
        "airport_drive_time": "30–45 minutes",
        "notes_from_indy": (
            "Chicago is reachable by short flight or drive from IND; flights are frequent into ORD and MDW from Indianapolis."
        ),
    },
    "Loyola University Chicago": {
        "airport_name": "Chicago O'Hare / Midway",
        "airport_code": "ORD / MDW",
        "airport_drive_time": "30–45 minutes",
        "notes_from_indy": (
            "Similar to UIC: frequent service between IND and Chicago-area airports, plus an easy drive option."
        ),
    },
    "North Carolina State University (NC State)": {
        "airport_name": "Raleigh–Durham International Airport",
        "airport_code": "RDU",
        "airport_drive_time": "20–25 minutes",
        "notes_from_indy": (
            "Typically a one-stop flight from IND via Charlotte (CLT), Atlanta (ATL), or another southeastern hub."
        ),
    },
    "University of North Carolina at Charlotte (Charlotte)": {
        "airport_name": "Charlotte Douglas International Airport",
        "airport_code": "CLT",
        "airport_drive_time": "20–25 minutes",
        "notes_from_indy": (
            "Often served from IND with non-stop or one-stop options into CLT; routes commonly include hubs like ATL or direct service depending on season."
        ),
    },
    "Virginia Commonwealth University (VCU)": {
        "airport_name": "Richmond International Airport",
        "airport_code": "RIC",
        "airport_drive_time": "20–25 minutes",
        "notes_from_indy": (
            "Usually a one-stop route from IND, frequently via Charlotte (CLT) or Atlanta (ATL)."
        ),
    },
    "Georgia Southern University": {
        "airport_name": "Savannah/Hilton Head International Airport",
        "airport_code": "SAV",
        "airport_drive_time": "45–55 minutes",
        "notes_from_indy": (
            "Most trips from IND involve one stop, commonly connecting through Atlanta (ATL) or Charlotte (CLT) into SAV."
        ),
    },
    "Northern Arizona University (NAU)": {
        "airport_name": "Flagstaff Pulliam Airport (alt: Phoenix Sky Harbor)",
        "airport_code": "FLG / PHX",
        "airport_drive_time": "10 minutes to FLG (about 2 hours to PHX)",
        "notes_from_indy": (
            "Common itineraries from IND connect via Phoenix (PHX) or Denver (DEN), then a short hop to FLG or a drive from PHX."
        ),
    },
    "Georgia State University": {
        "airport_name": "Hartsfield–Jackson Atlanta International Airport",
        "airport_code": "ATL",
        "airport_drive_time": "20–30 minutes",
        "notes_from_indy": (
            "Atlanta is a major hub with frequent service from IND; many flights are non-stop or one-stop into ATL."
        ),
    },
    "University of Denver": {
        "airport_name": "Denver International Airport",
        "airport_code": "DEN",
        "airport_drive_time": "30–40 minutes",
        "notes_from_indy": (
            "Typically reached from IND with non-stop or one-stop service into Denver (DEN)."
        ),
    },
    "Valparaiso University": {
        "airport_name": "Chicago O'Hare / Midway",
        "airport_code": "ORD / MDW",
        "airport_drive_time": "~1 hour to Chicago airports",
        "notes_from_indy": (
            "Valparaiso is within driving distance; many travelers use Chicago-area airports and then drive or take ground transport."
        ),
    },
    "University of Maryland, Baltimore County (UMBC)": {
        "airport_name": "Baltimore/Washington International Thurgood Marshall Airport",
        "airport_code": "BWI",
        "airport_drive_time": "15–20 minutes",
        "notes_from_indy": (
            "Most IND–BWI itineraries are non-stop or one-stop via hubs like Atlanta (ATL) or Charlotte (CLT); BWI is the primary airport for UMBC."
        ),
    },
}

# Indianapolis, IN approx coordinates
INDY_LAT = 39.7684
INDY_LON = -86.1581

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

SCHOOLS = [
    {
        "name": "Iowa State University",
        "short": "Iowa State",
        "city_state": "Ames, Iowa",
        "conference": "Big 12",
        "tier": "A",
        "offense_type": "5-1",
        "lat": 42.0269,
        "lon": -93.6465,
        "vb_opp_score": 2.3,  # default; will be overridden from pivot
        "geo_score": 2.0,
        "notes": "Large Big 12 program with strong academics and classic college-town environment.",
        "map_x": 0.58,  # normalized manual override for map plotting (optional)
        "map_y": 0.68,
    },
    {
        "name": "Kansas State University",
        "short": "Kansas State",
        "city_state": "Manhattan, Kansas",
        "conference": "Big 12",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 39.1911,
        "lon": -96.5795,
        "vb_opp_score": 2.3,
        "geo_score": 2.0,
        "notes": "Land-grant public with strong Ag/Engineering and traditional campus feel.",
        "map_x": 0.48,  # normalized manual override for map plotting (optional)
        "map_y": 0.57,
    },
    {
        "name": "University of Utah",
        "short": "Utah",
        "city_state": "Salt Lake City, Utah",
        "conference": "Big 12",
        "tier": "A",
        "offense_type": "5-1",
        "lat": 40.7649,
        "lon": -111.8421,
        "vb_opp_score": 2.3,
        "geo_score": 2.5,
        "notes": "Flagship research school with strong STEM and huge outdoors lifestyle upside.",
        "map_x": 0.25,  # normalized manual override for map plotting (optional)
        "map_y": 0.60,
    },
    {
        "name": "Florida State University",
        "short": "Florida State",
        "city_state": "Tallahassee, Florida",
        "conference": "ACC",
        "tier": "A",
        "offense_type": "5-1",
        "lat": 30.4441,
        "lon": -84.2994,
        "vb_opp_score": 2.0,
        "geo_score": 2.3,
        "notes": "Major athletics brand with strong academics and big-campus culture.",
        "map_x": 0.69,  # normalized manual override for map plotting (optional)
        "map_y": 0.30,
    },
    {
        "name": "Drake University",
        "short": "Drake",
        "city_state": "Des Moines, Iowa",
        "conference": "MVC",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 41.6010,
        "lon": -93.6570,
        "vb_opp_score": 2.7,
        "geo_score": 2.0,
        "notes": "Private mid-sized with strong business/law pathways and smaller, supportive environment.",
        "map_x": 0.55,  # normalized manual override for map plotting (optional)
        "map_y": 0.65,

    },
    {
        "name": "Florida Gulf Coast University",
        "short": "FGCU",
        "city_state": "Fort Myers, Florida",
        "conference": "ASUN",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 26.4667,
        "lon": -81.7733,
        "vb_opp_score": 2.7,
        "geo_score": 3.0,
        "notes": "Modern campus, warm climate, strong VB culture and good setter opportunity.",
        "map_x": 0.73,  # normalized manual override for map plotting (optional)
        "map_y": 0.18,
    },
    {
        "name": "University of Connecticut (UConn)",
        "short": "UConn",
        "city_state": "Storrs, Connecticut",
        "conference": "Big East",
        "tier": "A",
        "offense_type": "5-1",
        "lat": 41.8077,
        "lon": -72.2540,
        "vb_opp_score": 2.0,
        "geo_score": 2.0,
        "notes": "Flagship public with big school spirit and strong academic breadth.",
    },
    {
        "name": "Boise State University",
        "short": "Boise State",
        "city_state": "Boise, Idaho",
        "conference": "Mountain West",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 43.6020,
        "lon": -116.2060,
        "vb_opp_score": 3.0,
        "geo_score": 2.5,
        "notes": "Urban campus in a growing metro; strong setter need and good quality of life.",
        "map_x": 0.17,  # normalized manual override for map plotting (optional)
        "map_y": 0.72,
    },
    {
        "name": "Morehead State University",
        "short": "Morehead State",
        "city_state": "Morehead, Kentucky",
        "conference": "OVC",
        "tier": "B",
        "offense_type": "5-1",
        "lat": 38.1907,
        "lon": -83.4327,
        "vb_opp_score": 3.0,
        "geo_score": 2.0,
        "notes": "Smaller regional public; very high chance of early playing time.",
    },
    {
        "name": "University of Toledo",
        "short": "Toledo",
        "city_state": "Toledo, Ohio",
        "conference": "MAC",
        "tier": "B",
        "offense_type": "5-1",
        "lat": 41.6611,
        "lon": -83.6060,
        "vb_opp_score": 2.7,
        "geo_score": 2.0,
        "notes": "Mid-sized public with solid athletics and realistic setter opportunity.",
        "map_x": 0.72,  # normalized manual override for map plotting (optional)
        "map_y": 0.63,
    },
    {
        "name": "University of Northern Colorado",
        "short": "Northern Colorado",
        "city_state": "Greeley, Colorado",
        "conference": "Big Sky",
        "tier": "B",
        "offense_type": "5-1",
        "lat": 40.4073,
        "lon": -104.7006,
        "vb_opp_score": 2.7,
        "geo_score": 2.5,
        "notes": "Access to Colorado Front Range with good VB opportunity.",
    },
    {
        "name": "University of South Alabama",
        "short": "South Alabama",
        "city_state": "Mobile, Alabama",
        "conference": "Sun Belt",
        "tier": "B",
        "offense_type": "5-1",
        "lat": 30.6954,
        "lon": -88.1780,
        "vb_opp_score": 2.7,
        "geo_score": 2.3,
        "notes": "Warm climate, manageable campus size, good chance at real court time.",
        "map_x": 0.64,  # normalized manual override for map plotting (optional)
        "map_y": 0.30,
    },
    {
        "name": "University of Illinois Chicago (UIC)",
        "short": "UIC",
        "city_state": "Chicago, Illinois",
        "conference": "MVC",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 41.8708,
        "lon": -87.6505,
        "vb_opp_score": 2.7,
        "geo_score": 2.5,
        "notes": "Urban research school, high diversity, strong for city internships.",
        "map_x": 0.62,  # normalized manual override for map plotting (optional)
        "map_y": 0.68,
    },
    {
        "name": "Loyola University Chicago",
        "short": "Loyola Chicago",
        "city_state": "Chicago, Illinois",
        "conference": "MVC",
        "tier": "A-",
        "offense_type": "5-1",
        "lat": 41.9981,
        "lon": -87.6560,
        "vb_opp_score": 2.3,
        "geo_score": 2.5,
        "notes": "Jesuit private with strong health/business and beautiful lakeshore campus.",
        "map_x": 0.64,  # normalized manual override for map plotting (optional)
        "map_y": 0.65,
    },
    {
        "name": "North Carolina State University (NC State)",
        "short": "NC State",
        "city_state": "Raleigh, North Carolina",
        "conference": "ACC",
        "tier": "A",
        "offense_type": "5-1",
        "lat": 35.7847,
        "lon": -78.6821,
        "vb_opp_score": 2.0,
        "geo_score": 2.2,
        "notes": "STEM-heavy in the Research Triangle; very strong academically.",
    },
    {
        "name": "University of North Carolina at Charlotte (Charlotte)",
        "short": "UNC Charlotte",
        "city_state": "Charlotte, North Carolina",
        "conference": "AAC",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 35.3070,
        "lon": -80.7337,
        "vb_opp_score": 2.7,
        "geo_score": 2.5,
        "notes": "Growing public in major banking city; rising athletics profile.",
    },
    {
        "name": "Virginia Commonwealth University (VCU)",
        "short": "VCU",
        "city_state": "Richmond, Virginia",
        "conference": "A10",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 37.5495,
        "lon": -77.4520,
        "vb_opp_score": 2.5,
        "geo_score": 2.5,
        "notes": "Urban campus with national strength in arts/design and strong VB tradition.",
    },
    {
        "name": "Georgia Southern University",
        "short": "Georgia Southern",
        "city_state": "Statesboro, Georgia",
        "conference": "Sun Belt",
        "tier": "B",
        "offense_type": "5-1",
        "lat": 32.4220,
        "lon": -81.7930,
        "vb_opp_score": 2.7,
        "geo_score": 2.3,
        "notes": "Classic college-town feel with high opportunity for playing time.",
    },
    {
        "name": "Northern Arizona University (NAU)",
        "short": "Northern Arizona",
        "city_state": "Flagstaff, Arizona",
        "conference": "Big Sky",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 35.1894,
        "lon": -111.6513,
        "vb_opp_score": 3.0,
        "geo_score": 2.7,
        "notes": "Mountain-town, lifestyle school with major setter need.",
        "map_x": 0.22,  # normalized manual override for map plotting (optional)
        "map_y": 0.42,
    },
    {
        "name": "Georgia State University",
        "short": "Georgia State",
        "city_state": "Atlanta, Georgia",
        "conference": "Sun Belt",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 33.7537,
        "lon": -84.3857,
        "vb_opp_score": 2.7,
        "geo_score": 2.7,
        "notes": "Large urban campus in downtown Atlanta; great internships and city life.",
    },
    {
        "name": "University of Denver",
        "short": "Denver",
        "city_state": "Denver, Colorado",
        "conference": "Summit",
        "tier": "A-",
        "offense_type": "5-1",
        "lat": 39.6780,
        "lon": -104.9610,
        "vb_opp_score": 3.0,
        "geo_score": 2.7,
        "notes": "Selective private with strong business and international focus; high-level setter role.",
        "map_x": 0.35,  # normalized manual override for map plotting (optional)
        "map_y": 0.57,
    },
    {
        "name": "Valparaiso University",
        "short": "Valparaiso",
        "city_state": "Valparaiso, Indiana",
        "conference": "MVC",
        "tier": "B+",
        "offense_type": "5-1",
        "lat": 41.4630,
        "lon": -87.0440,
        "vb_opp_score": 2.7,
        "geo_score": 2.0,
        "notes": "Supportive private with strong engineering/nursing; good VB opportunity.",
        "map_x": 0.67,  # normalized manual override for map plotting (optional)
        "map_y": 0.65,
    },
    {
        "name": "University of Maryland, Baltimore County (UMBC)",
        "short": "UMBC",
        "city_state": "Baltimore, Maryland",
        "conference": "America East",
        "tier": "A-",
        "offense_type": "5-1",
        "lat": 39.2557,
        "lon": -76.7113,
        "vb_opp_score": 2.3,
        "geo_score": 2.2,
        "notes": "Research-oriented STEM-focused public; strong academic environment.",
    },
]

# -------------------------------------------------------------------
# LOGOS + NICHE-STYLE DATA
# -------------------------------------------------------------------

LOGO_MAP = {
    "Iowa State University": "Iowa_State_University.png",
    "Kansas State University": "Kansas State University.png",
    "University of Utah": "University_of_Utah.png",
    "Florida State University": "Florida_State_University.png",
    "Drake University": "Drake_University.png",
    "Florida Gulf Coast University": "Florida_Gulf_Coast_University.png",
    "University of Connecticut (UConn)": "University_Of_Connecticut.png",
    "Boise State University": "Boise_State_University_NEW.png",
    "Morehead State University": "Morehead_state_University_NEW.png",
    "University of Toledo": "Toledo_Rockets_logo.png",
    "University of Northern Colorado": "university_of_northern_colorado.png",
    "University of South Alabama": "University_of_South_Alabama.png",
    "University of Illinois Chicago (UIC)": "University_of_Illinois_Chicago_UIC_.png",
    "Loyola University Chicago": "Loyola_Ramblers_logo.png",
    "North Carolina State University (NC State)": "North_Carolina_State_University.png",
    "University of North Carolina at Charlotte (Charlotte)": "University_of_North_Carolina_at_Charlotte.png",
    "Virginia Commonwealth University (VCU)": "Virginia_Commonwealth_University.png",
    "Georgia Southern University": "Georgia_Southern_University.png",
    "Northern Arizona University (NAU)": "Northern_Arizona_University.png",
    "Georgia State University": "Georgia_State_University.png",
    "University of Denver": "University_of_Denver.png",
    "Valparaiso University": "Valparaiso_University.png",
    "University of Maryland, Baltimore County (UMBC)": "University_of_Maryland_Baltimore_County.png",
}

NICHE_DATA = {
    "Iowa State University": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B+",
        "summary": "Large Big 12 public with strong engineering, agriculture, and a classic campus-town atmosphere.",
        "review_pos": "\"Professors are supportive and there are many ways to get involved on campus.\"",
        "review_neg": "\"Intro classes can feel huge and it’s harder to get one-on-one help.\"",
    },
    "Kansas State University": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "A-",
        "summary": "Traditional land-grant university with tight-knit community and strong agriculture and engineering.",
        "review_pos": "\"Campus feels like a family and game days are a memorable experience.\"",
        "review_neg": "\"Manhattan is small, so entertainment options are limited off campus.\"",
    },
    "University of Utah": {
        "overall_grade": "A-",
        "academics_grade": "A",
        "value_grade": "B+",
        "summary": "Flagship research institution with excellent STEM and easy access to mountains and outdoor recreation.",
        "review_pos": "\"I love that skiing and hiking are so close to campus.\"",
        "review_neg": "\"Commuter culture can make it harder to form a tight social circle.\"",
    },
    "Florida State University": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B+",
        "summary": "Large ACC school known for strong academics, big-time athletics, and classic campus life.",
        "review_pos": "\"School spirit is huge and there’s always something happening.\"",
        "review_neg": "\"Advising and admin processes can feel slow and confusing.\"",
    },
    "Drake University": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B+",
        "summary": "Mid-sized private university with respected business, law, and journalism programs.",
        "review_pos": "\"Small classes mean professors actually know you and check in often.\"",
        "review_neg": "\"Campus can be quiet on weekends if you stay in the dorms.\"",
    },
    "Florida Gulf Coast University": {
        "overall_grade": "B+",
        "academics_grade": "B",
        "value_grade": "B+",
        "summary": "Modern campus in southwest Florida with warm weather and a growing academic profile.",
        "review_pos": "\"The lakefront campus feels like a resort and I love the boardwalks.\"",
        "review_neg": "\"Some majors still feel like they’re building depth in course options.\"",
    },
    "University of Connecticut (UConn)": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B+",
        "summary": "Flagship New England public university with strong research and huge basketball culture.",
        "review_pos": "\"UConn pride is real and there are excellent research opportunities.\"",
        "review_neg": "\"Storrs is rural, so you really need a car to get off campus.\"",
    },
    "Boise State University": {
        "overall_grade": "B+",
        "academics_grade": "B",
        "value_grade": "A-",
        "summary": "Urban campus in a growing city with solid academics and strong school spirit.",
        "review_pos": "\"Boise is friendly and there’s plenty to do downtown and outdoors.\"",
        "review_neg": "\"Advising quality really varies depending on your department.\"",
    },
    "Morehead State University": {
        "overall_grade": "B",
        "academics_grade": "B-",
        "value_grade": "B+",
        "summary": "Smaller regional public with close-knit community and strong education programs.",
        "review_pos": "\"Professors are approachable and classmates become like family.\"",
        "review_neg": "\"The town is tiny and you need a car for more variety.\"",
    },
    "University of Toledo": {
        "overall_grade": "B",
        "academics_grade": "B",
        "value_grade": "B+",
        "summary": "Mid-sized public university with solid engineering, pharmacy, and health sciences.",
        "review_pos": "\"Co-op opportunities in engineering have been a huge advantage.\"",
        "review_neg": "\"Some facilities and buildings feel older and in need of upgrades.\"",
    },
    "University of Northern Colorado": {
        "overall_grade": "B",
        "academics_grade": "B-",
        "value_grade": "B+",
        "summary": "Teaching-focused public university with strengths in education and performing arts.",
        "review_pos": "\"Class sizes are manageable and professors know who you are.\"",
        "review_neg": "\"The industrial parts of Greeley and the smell can be off-putting.\"",
    },
    "University of South Alabama": {
        "overall_grade": "B",
        "academics_grade": "B-",
        "value_grade": "B+",
        "summary": "Regional public with growing health sciences and warm Gulf Coast climate.",
        "review_pos": "\"Campus is pretty and professors are usually accessible.\"",
        "review_neg": "\"Campus life can feel quiet if you don’t join organizations.\"",
    },
    "University of Illinois Chicago (UIC)": {
        "overall_grade": "B+",
        "academics_grade": "A-",
        "value_grade": "B+",
        "summary": "Large urban research university with excellent health sciences and strong diversity.",
        "review_pos": "\"Being right in Chicago means endless internships and cultural experiences.\"",
        "review_neg": "\"Campus is spread out and navigating the city takes adjustment.\"",
    },
    "Loyola University Chicago": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B",
        "summary": "Jesuit private university with strong health, business, and environmental programs.",
        "review_pos": "\"Lake Shore campus views are amazing and professors are very supportive.\"",
        "review_neg": "\"Tuition is high and financial aid doesn’t always stretch far enough.\"",
    },
    "North Carolina State University (NC State)": {
        "overall_grade": "A-",
        "academics_grade": "A",
        "value_grade": "A-",
        "summary": "STEM-heavy research university in the heart of the Research Triangle.",
        "review_pos": "\"Engineering and CS connections with local companies are fantastic.\"",
        "review_neg": "\"Parking and housing are stressful because the area is growing fast.\"",
    },
    "University of North Carolina at Charlotte (Charlotte)": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "B+",
        "summary": "Growing urban research university tied closely to Charlotte’s banking industry.",
        "review_pos": "\"Modern campus and light rail make it easy to access the city.\"",
        "review_neg": "\"Rapid growth means some services and communication feel stretched.\"",
    },
    "Virginia Commonwealth University (VCU)": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "B",
        "summary": "Urban campus known for arts, design, and health sciences in downtown Richmond.",
        "review_pos": "\"Creative community is inspiring and the arts scene is strong.\"",
        "review_neg": "\"Campus is spread through the city, so it lacks a closed-campus feel.\"",
    },
    "Georgia Southern University": {
        "overall_grade": "B",
        "academics_grade": "B-",
        "value_grade": "B+",
        "summary": "Traditional southern college-town university with strong school spirit.",
        "review_pos": "\"Game days and campus events make it easy to feel included.\"",
        "review_neg": "\"Statesboro is small and can feel isolated if you like big cities.\"",
    },
    "Northern Arizona University (NAU)": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "B+",
        "summary": "Mountain-town campus with strong education and environmental programs.",
        "review_pos": "\"Flagstaff’s outdoors scene is incredible and campus feels welcoming.\"",
        "review_neg": "\"Housing and cost of living in Flagstaff are higher than expected.\"",
    },
    "Georgia State University": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "B+",
        "summary": "Large urban university embedded in downtown Atlanta with strong business programs.",
        "review_pos": "\"Internship access in Atlanta is unmatched and campus is in the city center.\"",
        "review_neg": "\"Very urban feel, so it lacks the classic closed-campus vibe.\"",
    },
    "University of Denver": {
        "overall_grade": "A-",
        "academics_grade": "A-",
        "value_grade": "B",
        "summary": "Selective private university with strong business, international studies, and law.",
        "review_pos": "\"Small classes, accessible professors, and Denver is a great city.\"",
        "review_neg": "\"Tuition and nearby housing are both very expensive.\"",
    },
    "Valparaiso University": {
        "overall_grade": "B+",
        "academics_grade": "B+",
        "value_grade": "B",
        "summary": "Private university with strong nursing and engineering programs and a faith-related heritage.",
        "review_pos": "\"Professors genuinely care and the community is close-knit.\"",
        "review_neg": "\"The town is quiet and social life can feel limited.\"",
    },
    "University of Maryland, Baltimore County (UMBC)": {
        "overall_grade": "A-",
        "academics_grade": "A",
        "value_grade": "B+",
        "summary": "STEM-focused public research university outside Baltimore and Washington, D.C.",
        "review_pos": "\"Academics are rigorous and research opportunities start early.\"",
        "review_neg": "\"Campus can feel more commuter-oriented and less like a traditional college town.\"",
    },
}


# -------------------------------------------------------------------
# ENRICH DATA FROM CSV: TEAM PIVOT (RPI, RECORD, OFFENSE, VB OPP)
# -------------------------------------------------------------------

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
        d_miles = haversine_miles(INDY_LAT, INDY_LON, s["lat"], s["lon"])
        s["flight_dist_mi"] = round(d_miles, 1)
        s["drive_dist_mi"] = round(d_miles * 1.15, 1)  # fudge factor for roads

        # Times
        s["drive_time_hr"] = round(s["drive_dist_mi"] / 60.0, 1)  # assume 60 mph avg
        s["flight_time_hr"] = round(s["flight_dist_mi"] / 450.0, 2)  # assume 450 mph avg jet

        # Travel difficulty: normalize ~ distance + some fudge
        base = s["drive_dist_mi"] / 10.0 + s["flight_dist_mi"] / 20.0
        s["travel_difficulty"] = int(min(100, max(10, base)))

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
    


# -------------------------------------------------------------------
# PDF BUILDING
# -------------------------------------------------------------------

# ---- US Map Flowable and Page ----

class USMapFlowable(Flowable):
    """
    Custom Flowable that draws a background map of the US and places a marker
    for each school based on lat/lon.

    Expects:
        image_path: Path to a PNG of a blank US map in landscape orientation.
        schools: list of dicts from SCHOOLS (must contain 'lat', 'lon', 'short').
    """
    def __init__(self, width, height, image_path, schools):
        super().__init__()
        self.width = width
        self.height = height
        self.image_path = image_path
        self.schools = schools

    def draw(self):
        c = self.canv

        # Draw the base US map image
        try:
            c.drawImage(
                str(self.image_path),
                0,
                0,
                width=self.width,
                height=self.height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            # If the image is missing, just draw a simple rectangle placeholder
            c.setStrokeColor(colors.grey)
            c.rect(0, 0, self.width, self.height)

        # Plot each school as a small circle marker
        for s in self.schools:
            # If manual normalized coordinates are provided, use them.
            map_x = s.get("map_x")
            map_y = s.get("map_y")

            if map_x is not None and map_y is not None:
                # Clamp to [0, 1] just in case
                norm_x = max(0.0, min(1.0, float(map_x)))
                norm_y = max(0.0, min(1.0, float(map_y)))
            else:
                # Fallback: derive from lat/lon using a simple rectangular projection.
                lat = s.get("lat")
                lon = s.get("lon")
                if lat is None or lon is None:
                    continue

                # Normalize lon/lat to 0–1 range based on US bounds
                # Clamp to stay inside the map box.
                norm_x = (lon - US_MIN_LON) / (US_MAX_LON - US_MIN_LON)
                norm_y = (lat - US_MIN_LAT) / (US_MAX_LAT - US_MIN_LAT)
                norm_x = max(0.0, min(1.0, norm_x))
                norm_y = max(0.0, min(1.0, norm_y))

            x = norm_x * self.width
            y = norm_y * self.height

            # Draw logo if available; otherwise draw a small circle
            fname = LOGO_MAP.get(s["name"], LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
            logo_path = PNG_DIR / fname if fname else None

            if logo_path and logo_path.exists():
                logo_w = 0.32 * inch
                logo_h = 0.25 * inch
                c.drawImage(
                    str(logo_path),
                    x - logo_w / 2,
                    y - logo_h / 2,
                    width=logo_w,
                    height=logo_h,
                    mask="auto",
                    preserveAspectRatio=True,
                )
            else:
                c.setFillColor(colors.red)
                c.setStrokeColor(colors.white)
                radius = 4
                c.circle(x, y, radius, fill=1, stroke=1)


def build_map_page(story, styles):
    """
    Add a page that shows a US map with a marker for each school.
    This should come immediately after the cover page.
    """
    heading = ParagraphStyle(
        "h_map",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        alignment=1,  # center
    )

    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("Target Schools – Geographic Overview", heading))
    story.append(Spacer(1, 0.3 * inch))

    # Create the map flowable. Leave margins on the sides.
    map_width = 7.2 * inch
    map_height = map_width * (665 / 1024)  # preserve source image aspect

    if US_MAP_IMAGE.exists():
        map_flowable = USMapFlowable(
            width=map_width,
            height=map_height,
            image_path=US_MAP_IMAGE,
            schools=SCHOOLS,
        )
        story.append(map_flowable)
    else:
        story.append(Paragraph("Map image not found; skipping map page.", styles["BodyText"]))

    story.append(PageBreak())

def build_cover_page(story, styles):
    """Add cover page to story."""
    title_style = ParagraphStyle(
        'title',
        parent=styles['Title'],
        alignment=1,
        fontSize=24,
        leading=30,
    )
    subtitle_style = ParagraphStyle(
        'subtitle',
        parent=styles['BodyText'],
        alignment=1,
        fontSize=12,
        leading=16,
    )
    personal_style = ParagraphStyle(
        'personal',
        parent=styles['BodyText'],
        alignment=1,
        fontSize=11,
        leading=14,
    )

    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("2025 Transfer Opportunity Analysis – Setter Edition", title_style))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "A comprehensive analysis of setter depth, opportunity, culture & travel logistics",
        subtitle_style,
    ))
    story.append(Spacer(1, 0.35 * inch))

    # 5-column grid of logos (hardcoded order from SCHOOLS)
    cols = 5
    logo_width = 1.1 * inch
    logo_height = 0.9 * inch
    cells = []
    row = []

    for idx, s in enumerate(SCHOOLS):
        fname = LOGO_MAP.get(s["name"], LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
        if fname:
            path = PNG_DIR / fname
            if path.exists():
                cell = Image(str(path), width=logo_width, height=logo_height)
            else:
                cell = Paragraph(s["short"], styles['BodyText'])
        else:
            cell = Paragraph(s["short"], styles['BodyText'])
        row.append(cell)
        if (idx + 1) % cols == 0:
            cells.append(row)
            row = []

    if row:
        while len(row) < cols:
            row.append("")
        cells.append(row)

    table = Table(
        cells,
        colWidths=[(7.5 * inch) / cols] * cols
    )
    table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "Prepared for <b>Molly Beatty</b> – 5'11\" Right-Handed Setter – Class of 2029",
        personal_style,
    ))
    story.append(PageBreak())


def build_school_pages(story, styles):
    """Add one page per school with logo, profile, Niche data, travel, notes, and 2026 roster."""
    heading = ParagraphStyle(
        'h_school',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
    )
    sub = ParagraphStyle(
        'sub_school',
        parent=styles['BodyText'],
        fontSize=10,
        leading=13,
    )
    roster_heading = ParagraphStyle(
        'h_roster',
        parent=styles['Heading3'],
        fontSize=11,
        leading=13,
        alignment=1,  # center
    )
    notes_heading = ParagraphStyle(
        'h_notes',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        alignment=1,
    )

    def add_notes_page(school_name: str):
        story.append(PageBreak())
        story.append(Paragraph(f"{school_name} – Notes", notes_heading))
        story.append(Spacer(1, 0.15 * inch))
        # Notebook-style lines
        line_count = 32
        lines = [[""] for _ in range(line_count)]
        notes_table = Table(lines, colWidths=[6.5 * inch])
        notes_table.setStyle(TableStyle([
            # Horizontal blue lines
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#7da7d9")),
            # Left margin rule (light red), offset ~1" from left
            ("LINEBEFORE", (0, 0), (0, -1), 0.75, colors.HexColor("#d77a7a")),
            # Outer blue border
            ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#7da7d9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWHEIGHT", (0, 0), (-1, -1), 0.30 * inch),
        ]))
        story.append(notes_table)
        story.append(PageBreak())

    for s in SCHOOLS:
        story.append(Paragraph(s["name"], heading))
        story.append(Spacer(1, 0.08 * inch))

        # Logo + basic info + Niche snapshot
        fname = LOGO_MAP.get(s["name"], LOGO_MAP.get(s["name"].replace(" (UConn)", ""), None))
        if fname:
            path = PNG_DIR / fname
            if path.exists():
                img = Image(str(path), width=1.5 * inch, height=1.1 * inch)
                niche = NICHE_DATA.get(s["name"], {})
                overall_grade = niche.get("overall_grade", "N/A")
                academics_grade = niche.get("academics_grade", "N/A")
                value_grade = niche.get("value_grade", "N/A")
                rpi_display = (
                    f"{int(s['rpi_rank'])}"
                    if isinstance(s.get("rpi_rank"), (int, float))
                    else "N/A"
                )
                record_display = s.get("record", "N/A")
                politics_label = s.get("politics_label") or "N/A"

                left_para = Paragraph(
                    f"<b>Location:</b> {s['city_state']}<br/>"
                    f"<b>Conference:</b> {s['conference']}<br/>"
                    f"<b>Academic Tier:</b> {s['tier']}<br/>"
                    f"<b>Offense Type:</b> {s['offense_type']}<br/>"
                    f"<b>RPI Rank:</b> {rpi_display}<br/>"
                    f"<b>Record:</b> {record_display}<br/>"
                    f"<b>Fit Score:</b> {s['fit_score']} / 3.0<br/>"
                    f"<b>Campus politics:</b> {politics_label}",
                    sub
                )

                right_para = Paragraph(
                    f"<b>Niche Snapshot:</b><br/>"
                    f"Overall: {overall_grade} &nbsp; "
                    f"Academics: {academics_grade} &nbsp; "
                    f"Value: {value_grade}",
                    sub
                )

                info_table = Table([[img, left_para], ["", right_para]])
                info_table.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(info_table)
            else:
                story.append(Paragraph(f"[Logo missing: {fname}]", styles['BodyText']))
        else:
            story.append(Paragraph("[Logo not mapped]", styles['BodyText']))

        story.append(Spacer(1, 0.1 * inch))

        # Travel info
        travel_text = (
            f"<b>Travel from Indianapolis:</b><br/>"
            f"Approx. driving distance: {s['drive_dist_mi']} miles "
            f"(~{s['drive_time_hr']} hrs)<br/>"
            f"Great-circle flight distance: {s['flight_dist_mi']} miles "
            f"(~{s['flight_time_hr']} hrs in-air)<br/>"
            f"Travel Difficulty Score: {s['travel_difficulty']} / 100"
        )
        story.append(Paragraph(travel_text, sub))
        story.append(Spacer(1, 0.1 * inch))

        # Air travel details for farther schools (boxed table)
        info = AIRPORT_INFO.get(s["name"])
        if info and s.get("drive_dist_mi", 0) > 350:
            airport_name = info["airport_name"]
            airport_code = info["airport_code"]
            drive_time = info.get("airport_drive_time", "N/A")
            notes = info["notes_from_indy"]

            air_rows = [
                [Paragraph("<b>Air Travel Notes</b>", sub)],
                [Paragraph(f"Nearest major airport: {airport_name} ({airport_code})", sub)],
                [Paragraph(f"Approx. drive to airport: {drive_time}", sub)],
                [Paragraph(f"From IND: {notes}", sub)],
            ]

            air_table = Table(
                air_rows,
                colWidths=[6.5 * inch],
            )
            air_table.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.75, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))

            story.append(air_table)
            story.append(Spacer(1, 0.12 * inch))

        # Coach contacts (first 3 from pivot, if available)
        coaches = s.get("coaches", [])
        if coaches:
            story.append(Paragraph("<b>Staff Contacts (top 3)</b>", sub))
            coach_rows = [["Name", "Title", "Contact"]]
            for c in coaches[:3]:
                contact_lines = []
                email = c.get("email", "")
                phone = normalize_phone(c.get("phone", ""))
                if email:
                    contact_lines.append(escape(email))
                if phone:
                    contact_lines.append(escape(phone))
                contact_html = "<br/>".join(contact_lines) if contact_lines else ""
                contact = Paragraph(contact_html, sub) if contact_html else Paragraph("", sub)
                coach_rows.append([
                    c.get("name", ""),
                    c.get("title", ""),
                    contact,
                ])
            coach_table = Table(
                coach_rows,
                colWidths=[1.9*inch, 1.7*inch, 2.6*inch],
            )
            coach_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
            ]))
            story.append(coach_table)
            story.append(Spacer(1, 0.1 * inch))

        # Niche-style summary and reviews
        niche = NICHE_DATA.get(s["name"], {})
        summary = niche.get("summary", "")
        review_pos = niche.get("review_pos", "")
        review_neg = niche.get("review_neg", "")

        if summary:
            story.append(Paragraph(f"<b>Campus & Academic Vibe:</b> {summary}", sub))
            story.append(Spacer(1, 0.08 * inch))

        if review_pos:
            story.append(Paragraph(f"<b>Student Review (Positive):</b> {review_pos}", sub))
            story.append(Spacer(1, 0.05 * inch))
        if review_neg:
            story.append(Paragraph(f"<b>Student Review (Critical):</b> {review_neg}", sub))
            story.append(Spacer(1, 0.08 * inch))

        # Program-specific notes
        story.append(Paragraph(f"<b>Program & Fit Notes:</b> {s['notes']}", sub))

        # 2026 Roster table
        players = s.get("roster_2026", [])
        if players:
            # Move roster to a dedicated page to improve fit
            story.append(PageBreak())
            story.append(Paragraph(s["name"], heading))
            story.append(Spacer(1, 0.05 * inch))
            story.append(Paragraph(
                "Projected 2026 Roster Snapshot (key contributors)",
                roster_heading,
            ))
            story.append(Spacer(1, 0.05 * inch))

            data = [["Name", "Class", "Pos", "Height", "Kills", "Assists", "Digs"]]
            for p in players:
                data.append([
                    p.get("name", ""),
                    p.get("class", ""),
                    p.get("position", ""),
                    p.get("height", ""),
                    p.get("kills", ""),
                    p.get("assists", ""),
                    p.get("digs", ""),
                ])

            roster_table = Table(
                data,
                colWidths=[1.8*inch, 0.65*inch, 0.7*inch, 0.7*inch, 0.75*inch, 0.8*inch, 0.7*inch],
                hAlign="CENTER",
            )
            roster_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ]))
            story.append(roster_table)

        # Notes page for this school
        add_notes_page(s["name"])


def build_fit_score_table(story, styles):
    """Add a table ranking schools by Fit Score (with RPI)."""
    heading = ParagraphStyle(
        'h_fit',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
    )
    story.append(Paragraph("Overall Fit Score Ranking", heading))
    story.append(Spacer(1, 0.15 * inch))

    sorted_schools = sorted(SCHOOLS, key=lambda x: x["fit_score"], reverse=True)
    data = [["Rank", "School", "Tier", "RPI", "Fit Score", "VB Opp", "Geo Score"]]
    for i, s in enumerate(sorted_schools, start=1):
        rpi_display = (
            f"{int(s['rpi_rank'])}"
            if isinstance(s.get("rpi_rank"), (int, float))
            else "N/A"
        )
        data.append([
            i,
            s["short"],
            s["tier"],
            rpi_display,
            f"{s['fit_score']:.2f}",
            f"{s['vb_opp_score']:.1f}",
            f"{s['geo_score']:.1f}",
        ])

    table = Table(
        data,
        colWidths=[0.5*inch, 2.1*inch, 0.6*inch, 0.7*inch, 0.9*inch, 0.9*inch, 0.9*inch],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
    ]))

    story.append(table)
    story.append(PageBreak())


def build_travel_matrix(story, styles):
    """Add a travel distance matrix."""
    heading = ParagraphStyle(
        'h_travel',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
    )
    story.append(Paragraph("Travel Distance & Difficulty Matrix (From Indianapolis, IN)", heading))
    story.append(Spacer(1, 0.15 * inch))

    data = [[
        "School",
        "Drive (mi)",
        "Drive (hrs)",
        "Flight (mi)",
        "Flight (hrs)",
        "Travel Diff.",
    ]]

    for s in sorted(SCHOOLS, key=lambda x: x["drive_dist_mi"]):
        data.append([
            s["short"],
            f"{s['drive_dist_mi']:.0f}",
            f"{s['drive_time_hr']:.1f}",
            f"{s['flight_dist_mi']:.0f}",
            f"{s['flight_time_hr']:.2f}",
            str(s["travel_difficulty"]),
        ])

    table = Table(data, colWidths=[2.2*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 1.0*inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
    ]))

    story.append(table)
    story.append(PageBreak())


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

def main():
    ensure_logos_unzipped()
    enrich_schools_from_csv()
    enrich_rosters_from_csv()
    compute_travel_and_fit()

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=0.45 * inch,
        rightMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.55 * inch,
    )
    story = []

    # Build sections (cover + map + tables + school pages, with hard-coded order)
    build_cover_page(story, styles)
    build_map_page(story, styles)
    build_fit_score_table(story, styles)
    build_travel_matrix(story, styles)
    build_school_pages(story, styles)

    doc.build(story)
    print(f"\nUltimate guide written to: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
