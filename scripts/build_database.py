"""
Build or refresh the local volleyball database from the scraped CSV/JSON assets.

Usage examples:
  python scripts/build_database.py --season 2025
  python scripts/build_database.py --season 2025 --db data/vb.db --drop-season
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


def _coerce_float(value):
    if pd.isna(value):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def _height_to_inches(raw: str | float | None) -> int | None:
    """Convert heights like '6-2' or '5-10' to total inches."""
    if raw is None or pd.isna(raw):
        return None
    text = str(raw).strip()
    if not text:
        return None
    for sep in ("-", "’", "'", "′"):
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                feet, inches = map(int, parts)
                return feet * 12 + inches
    if text.isdigit():
        # Already an inch value
        return int(text)
    return None


def init_db(conn: sqlite3.Connection):
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS conferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS airports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ident TEXT,
            type TEXT,
            name TEXT,
            latitude REAL,
            longitude REAL,
            iso_country TEXT,
            iso_region TEXT,
            municipality TEXT,
            iata_code TEXT UNIQUE,
            local_code TEXT,
            score INTEGER,
            last_updated TEXT
        );

        CREATE TABLE IF NOT EXISTS scorecard_schools (
            unitid INTEGER PRIMARY KEY,
            instnm TEXT,
            city TEXT,
            state TEXT,
            adm_rate REAL,
            sat_avg REAL,
            tuition_in REAL,
            tuition_out REAL,
            cost_t4 REAL,
            grad_rate REAL,
            retention_rate REAL,
            pct_pell REAL,
            pct_fulltime_fac REAL,
            median_earnings REAL
        );

        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            short_name TEXT,
            conference_id INTEGER REFERENCES conferences(id),
            city TEXT,
            state TEXT,
            url TEXT,
            stats_url TEXT,
            tier TEXT,
            political_label TEXT,
            latitude REAL,
            longitude REAL,
            airport_code TEXT REFERENCES airports(iata_code),
            airport_name TEXT,
            airport_drive_time TEXT,
            airport_notes TEXT,
            aliases_json TEXT,
            niche_json TEXT,
            notes TEXT,
            risk_watchouts TEXT,
            scorecard_unitid INTEGER REFERENCES scorecard_schools(unitid),
            scorecard_confidence TEXT,
            scorecard_match_name TEXT,
            coaches_json TEXT,
            logo_filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            position TEXT,
            class_year TEXT,
            height_inches INTEGER,
            season INTEGER NOT NULL,
            UNIQUE(team_id, name, season)
        );

        CREATE TABLE IF NOT EXISTS player_stats (
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            season INTEGER NOT NULL,
            ms REAL,
            mp REAL,
            sp REAL,
            pts REAL,
            pts_per_set REAL,
            k REAL,
            k_per_set REAL,
            ae REAL,
            ta REAL,
            hit_pct REAL,
            assists REAL,
            assists_per_set REAL,
            sa REAL,
            sa_per_set REAL,
            se REAL,
            digs REAL,
            digs_per_set REAL,
            re REAL,
            tre REAL,
            rec_pct REAL,
            bs REAL,
            ba REAL,
            tb REAL,
            blocks_per_set REAL,
            bhe REAL,
            PRIMARY KEY (player_id, season)
        );

        CREATE TABLE IF NOT EXISTS ingestion_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            season INTEGER,
            rosters_path TEXT,
            teams_path TEXT,
            airports_path TEXT,
            scorecard_path TEXT,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id, season);
        CREATE INDEX IF NOT EXISTS idx_player_stats_season ON player_stats(season);
        CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference_id);
        """
    )
    conn.commit()


def upsert_conference(conn: sqlite3.Connection, name: str | None) -> int | None:
    if not name:
        return None
    cur = conn.execute(
        "INSERT INTO conferences(name) VALUES (?) ON CONFLICT(name) DO NOTHING RETURNING id",
        (name,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute("SELECT id FROM conferences WHERE name = ?", (name,))
    return cur.fetchone()[0]


def load_airports(conn: sqlite3.Connection, path: Path, airport_types: Tuple[str, ...]):
    if not path.exists():
        raise FileNotFoundError(path)
    cols = [
        "ident",
        "type",
        "name",
        "latitude_deg",
        "longitude_deg",
        "iso_country",
        "iso_region",
        "municipality",
        "iata_code",
        "local_code",
        "score",
        "last_updated",
    ]
    df = pd.read_csv(path, usecols=cols)
    df = df[df["type"].isin(airport_types)]
    df = df[df["iso_country"] == "US"]
    records = [
        (
            row.ident,
            row.type,
            row.name,
            _coerce_float(row.latitude_deg),
            _coerce_float(row.longitude_deg),
            row.iso_country,
            row.iso_region,
            row.municipality,
            row.iata_code,
            row.local_code,
            _coerce_float(row.score),
            row.last_updated,
        )
        for row in df.itertuples(index=False)
        if pd.notna(row.iata_code)
    ]
    conn.executemany(
        """
        INSERT INTO airports (
            ident, type, name, latitude, longitude, iso_country, iso_region,
            municipality, iata_code, local_code, score, last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(iata_code) DO UPDATE SET
            ident=excluded.ident,
            type=excluded.type,
            name=excluded.name,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            iso_country=excluded.iso_country,
            iso_region=excluded.iso_region,
            municipality=excluded.municipality,
            local_code=excluded.local_code,
            score=excluded.score,
            last_updated=excluded.last_updated
        """,
        records,
    )
    conn.commit()


def load_scorecard(conn: sqlite3.Connection, path: Path, valid_unitids: Iterable[int]):
    if not path.exists():
        raise FileNotFoundError(path)
    cols = [
        "UNITID",
        "INSTNM",
        "CITY",
        "STABBR",
        "ADM_RATE",
        "SAT_AVG",
        "TUITIONFEE_IN",
        "TUITIONFEE_OUT",
        "COSTT4_A",
        "C150_4",
        "RET_FT4",
        "PCTPELL",
        "PFTFAC",
        "MD_EARN_WNE_P10",
    ]
    df = pd.read_csv(path, usecols=cols, low_memory=False)
    df = df[df["UNITID"].isin(valid_unitids)]
    records = [
        (
            int(row.UNITID),
            row.INSTNM,
            row.CITY,
            row.STABBR,
            _coerce_float(row.ADM_RATE),
            _coerce_float(row.SAT_AVG),
            _coerce_float(row.TUITIONFEE_IN),
            _coerce_float(row.TUITIONFEE_OUT),
            _coerce_float(row.COSTT4_A),
            _coerce_float(row.C150_4),
            _coerce_float(row.RET_FT4),
            _coerce_float(row.PCTPELL),
            _coerce_float(row.PFTFAC),
            _coerce_float(row.MD_EARN_WNE_P10),
        )
        for row in df.itertuples(index=False)
    ]
    conn.executemany(
        """
        INSERT INTO scorecard_schools (
            unitid, instnm, city, state, adm_rate, sat_avg, tuition_in,
            tuition_out, cost_t4, grad_rate, retention_rate, pct_pell,
            pct_fulltime_fac, median_earnings
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(unitid) DO UPDATE SET
            instnm=excluded.instnm,
            city=excluded.city,
            state=excluded.state,
            adm_rate=excluded.adm_rate,
            sat_avg=excluded.sat_avg,
            tuition_in=excluded.tuition_in,
            tuition_out=excluded.tuition_out,
            cost_t4=excluded.cost_t4,
            grad_rate=excluded.grad_rate,
            retention_rate=excluded.retention_rate,
            pct_pell=excluded.pct_pell,
            pct_fulltime_fac=excluded.pct_fulltime_fac,
            median_earnings=excluded.median_earnings
        """,
        records,
    )
    conn.commit()


def load_teams(conn: sqlite3.Connection, path: Path, teams_data=None):
    if teams_data is None:
        if not path.exists():
            raise FileNotFoundError(path)
        teams_data = json.load(open(path))
    for team in teams_data:
        conference_id = upsert_conference(conn, team.get("conference"))
        city = team.get("city")
        state = team.get("state")
        if not city or not state:
            city_state = team.get("city_state") or ""
            if "," in city_state:
                city, state = [part.strip() for part in city_state.split(",", 1)]
        logo_filename = (team.get("logo_map_name") or "").strip() or None
        conn.execute(
            """
            INSERT INTO teams (
                name, short_name, conference_id, city, state, url, stats_url,
                tier, political_label, latitude, longitude, airport_code,
                airport_name, airport_drive_time, airport_notes, aliases_json,
                niche_json, notes, risk_watchouts, scorecard_unitid,
                scorecard_confidence, scorecard_match_name, coaches_json, logo_filename, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                short_name=excluded.short_name,
                conference_id=excluded.conference_id,
                city=excluded.city,
                state=excluded.state,
                url=excluded.url,
                stats_url=excluded.stats_url,
                tier=excluded.tier,
                political_label=excluded.political_label,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                airport_code=excluded.airport_code,
                airport_name=excluded.airport_name,
                airport_drive_time=excluded.airport_drive_time,
                airport_notes=excluded.airport_notes,
                aliases_json=excluded.aliases_json,
                niche_json=excluded.niche_json,
                notes=excluded.notes,
                risk_watchouts=excluded.risk_watchouts,
                scorecard_unitid=excluded.scorecard_unitid,
                scorecard_confidence=excluded.scorecard_confidence,
                scorecard_match_name=excluded.scorecard_match_name,
                coaches_json=excluded.coaches_json,
                logo_filename=excluded.logo_filename,
                updated_at=excluded.updated_at
            """,
            (
                team.get("team"),
                team.get("short_name"),
                conference_id,
                city,
                state,
                team.get("url"),
                team.get("stats_url"),
                team.get("tier"),
                team.get("political_label"),
                _coerce_float(team.get("lat")),
                _coerce_float(team.get("lon")),
                team.get("airport_code"),
                team.get("airport_name"),
                team.get("airport_drive_time"),
                team.get("airport_notes"),
                json.dumps(team.get("team_name_aliases", [])),
                json.dumps(team.get("niche")),
                team.get("notes"),
                team.get("risk_watchouts"),
                team.get("scorecard_unitid") or (team.get("scorecard") or {}).get("unitid"),
                team.get("scorecard_confidence") or (team.get("scorecard") or {}).get("confidence"),
                team.get("scorecard_match_name"),
                json.dumps(team.get("coaches", [])),
                logo_filename,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    conn.commit()


def _team_id_map(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute("SELECT id, name FROM teams")
    return {name: id_ for (id_, name) in cur.fetchall()}


def _delete_season(conn: sqlite3.Connection, season: int):
    conn.execute("DELETE FROM player_stats WHERE season = ?", (season,))
    conn.execute("DELETE FROM players WHERE season = ?", (season,))
    conn.commit()


def load_rosters(conn: sqlite3.Connection, path: Path, season: int):
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    team_ids = _team_id_map(conn)
    inserted_players = 0
    inserted_stats = 0
    stat_fields = {
        "MS": "ms",
        "MP": "mp",
        "SP": "sp",
        "PTS": "pts",
        "PTS/S": "pts_per_set",
        "K": "k",
        "K/S": "k_per_set",
        "AE": "ae",
        "TA": "ta",
        "HIT%": "hit_pct",
        "A": "assists",
        "A/S": "assists_per_set",
        "SA": "sa",
        "SA/S": "sa_per_set",
        "SE": "se",
        "D": "digs",
        "D/S": "digs_per_set",
        "RE": "re",
        "TRE": "tre",
        "Rec%": "rec_pct",
        "BS": "bs",
        "BA": "ba",
        "TB": "tb",
        "B/S": "blocks_per_set",
        "BHE": "bhe",
    }
    for _, row in df.iterrows():
        team_id = team_ids.get(row["Team"])
        if not team_id:
            continue
        player_row = (
            team_id,
            row["Name"],
            row.get("Position"),
            row.get("Class"),
            _height_to_inches(row.get("Height")),
            season,
        )
        conn.execute(
            """
            INSERT INTO players (team_id, name, position, class_year, height_inches, season)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, name, season) DO UPDATE SET
                position=excluded.position,
                class_year=excluded.class_year,
                height_inches=excluded.height_inches
            """,
            player_row,
        )
        inserted_players += 1
        player_id = conn.execute(
            "SELECT id FROM players WHERE team_id = ? AND name = ? AND season = ?",
            (team_id, row["Name"], season),
        ).fetchone()[0]
        stat_values = {alias: _coerce_float(row.get(col)) for col, alias in stat_fields.items()}
        stats_row = (
            player_id,
            season,
            stat_values["ms"],
            stat_values["mp"],
            stat_values["sp"],
            stat_values["pts"],
            stat_values["pts_per_set"],
            stat_values["k"],
            stat_values["k_per_set"],
            stat_values["ae"],
            stat_values["ta"],
            stat_values["hit_pct"],
            stat_values["assists"],
            stat_values["assists_per_set"],
            stat_values["sa"],
            stat_values["sa_per_set"],
            stat_values["se"],
            stat_values["digs"],
            stat_values["digs_per_set"],
            stat_values["re"],
            stat_values["tre"],
            stat_values["rec_pct"],
            stat_values["bs"],
            stat_values["ba"],
            stat_values["tb"],
            stat_values["blocks_per_set"],
            stat_values["bhe"],
        )
        conn.execute(
            """
            INSERT INTO player_stats (
                player_id, season, ms, mp, sp, pts, pts_per_set, k, k_per_set,
                ae, ta, hit_pct, assists, assists_per_set, sa, sa_per_set, se,
                digs, digs_per_set, re, tre, rec_pct, bs, ba, tb, blocks_per_set, bhe
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, season) DO UPDATE SET
                ms=excluded.ms,
                mp=excluded.mp,
                sp=excluded.sp,
                pts=excluded.pts,
                pts_per_set=excluded.pts_per_set,
                k=excluded.k,
                k_per_set=excluded.k_per_set,
                ae=excluded.ae,
                ta=excluded.ta,
                hit_pct=excluded.hit_pct,
                assists=excluded.assists,
                assists_per_set=excluded.assists_per_set,
                sa=excluded.sa,
                sa_per_set=excluded.sa_per_set,
                se=excluded.se,
                digs=excluded.digs,
                digs_per_set=excluded.digs_per_set,
                re=excluded.re,
                tre=excluded.tre,
                rec_pct=excluded.rec_pct,
                bs=excluded.bs,
                ba=excluded.ba,
                tb=excluded.tb,
                blocks_per_set=excluded.blocks_per_set,
                bhe=excluded.bhe
            """,
            stats_row,
        )
        inserted_stats += 1
    conn.commit()
    return inserted_players, inserted_stats


def parse_args():
    parser = argparse.ArgumentParser(description="Build SQLite database from scraped assets.")
    parser.add_argument("--db", default="data/vb.db", help="SQLite database path to create/update.")
    parser.add_argument("--season", type=int, required=True, help="Season year for roster/stats rows.")
    parser.add_argument("--teams", default="settings/teams.json", help="Teams JSON path.")
    parser.add_argument("--rosters", default="exports/rosters_and_stats.csv", help="Roster + stats CSV path.")
    parser.add_argument("--airports", default="external_data/airports_us.csv", help="Airports CSV path.")
    parser.add_argument(
        "--airport-types",
        nargs="+",
        default=["large_airport", "medium_airport"],
        help="Airport types to import.",
    )
    parser.add_argument(
        "--scorecard",
        default="external_data/college_scorecard_most_recent.csv",
        help="College Scorecard CSV path.",
    )
    parser.add_argument(
        "--drop-season",
        action="store_true",
        help="Delete existing players/stats for the given season before loading.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)

    if not Path(args.teams).exists():
        raise FileNotFoundError(args.teams)
    teams_data = json.load(open(args.teams))
    team_unitids = []
    for team in teams_data:
        candidate = team.get("scorecard_unitid") or (team.get("scorecard") or {}).get("unitid")
        if candidate is None:
            continue
        try:
            team_unitids.append(int(candidate))
        except Exception:
            continue

    run_id = conn.execute(
        """
        INSERT INTO ingestion_runs (season, rosters_path, teams_path, airports_path, scorecard_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (args.season, str(args.rosters), str(args.teams), str(args.airports), str(args.scorecard)),
    ).lastrowid

    load_airports(conn, Path(args.airports), tuple(args.airport_types))
    if team_unitids:
        load_scorecard(conn, Path(args.scorecard), team_unitids)
    load_teams(conn, Path(args.teams), teams_data=teams_data)

    if args.drop_season:
        _delete_season(conn, args.season)

    players_count, stats_count = load_rosters(conn, Path(args.rosters), args.season)

    conn.execute(
        "UPDATE ingestion_runs SET finished_at = ? , notes = ? WHERE id = ?",
        (
            datetime.now(timezone.utc).isoformat(),
            f"players: {players_count}, stats: {stats_count}",
            run_id,
        ),
    )
    conn.commit()
    conn.close()
    print(f"Done. Players upserted: {players_count}, stats upserted: {stats_count}")


if __name__ == "__main__":
    main()
