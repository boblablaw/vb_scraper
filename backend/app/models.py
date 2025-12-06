from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Conference(Base):
    __tablename__ = "conferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

    teams: Mapped[List["Team"]] = relationship("Team", back_populates="conference")


class Airport(Base):
    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(primary_key=True)
    ident: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    iso_country: Mapped[Optional[str]] = mapped_column(String)
    iso_region: Mapped[Optional[str]] = mapped_column(String)
    municipality: Mapped[Optional[str]] = mapped_column(String)
    iata_code: Mapped[Optional[str]] = mapped_column(String, unique=True)
    local_code: Mapped[Optional[str]] = mapped_column(String)
    score: Mapped[Optional[float]] = mapped_column(Float)
    last_updated: Mapped[Optional[str]] = mapped_column(String)

    teams: Mapped[List["Team"]] = relationship(
        "Team",
        primaryjoin="Airport.iata_code==Team.airport_code",
        viewonly=True,
    )


class ScorecardSchool(Base):
    __tablename__ = "scorecard_schools"

    unitid: Mapped[int] = mapped_column(primary_key=True)
    instnm: Mapped[Optional[str]] = mapped_column(String)
    city: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    adm_rate: Mapped[Optional[float]] = mapped_column(Float)
    sat_avg: Mapped[Optional[float]] = mapped_column(Float)
    tuition_in: Mapped[Optional[float]] = mapped_column(Float)
    tuition_out: Mapped[Optional[float]] = mapped_column(Float)
    cost_t4: Mapped[Optional[float]] = mapped_column(Float)
    grad_rate: Mapped[Optional[float]] = mapped_column(Float)
    retention_rate: Mapped[Optional[float]] = mapped_column(Float)
    pct_pell: Mapped[Optional[float]] = mapped_column(Float)
    pct_fulltime_fac: Mapped[Optional[float]] = mapped_column(Float)
    median_earnings: Mapped[Optional[float]] = mapped_column(Float)

    teams: Mapped[List["Team"]] = relationship(
        "Team",
        primaryjoin="ScorecardSchool.unitid==Team.scorecard_unitid",
        viewonly=True,
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    short_name: Mapped[Optional[str]] = mapped_column(String)
    conference_id: Mapped[Optional[int]] = mapped_column(ForeignKey("conferences.id"))
    city: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String)
    stats_url: Mapped[Optional[str]] = mapped_column(String)
    tier: Mapped[Optional[str]] = mapped_column(String)
    political_label: Mapped[Optional[str]] = mapped_column(String)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    airport_code: Mapped[Optional[str]] = mapped_column(ForeignKey("airports.iata_code"))
    airport_name: Mapped[Optional[str]] = mapped_column(String)
    airport_drive_time: Mapped[Optional[str]] = mapped_column(String)
    airport_notes: Mapped[Optional[str]] = mapped_column(Text)
    aliases_json: Mapped[Optional[str]] = mapped_column(Text)
    niche_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    risk_watchouts: Mapped[Optional[str]] = mapped_column(Text)
    scorecard_unitid: Mapped[Optional[int]] = mapped_column(ForeignKey("scorecard_schools.unitid"))
    scorecard_confidence: Mapped[Optional[str]] = mapped_column(String)
    scorecard_match_name: Mapped[Optional[str]] = mapped_column(String)
    coaches_json: Mapped[Optional[str]] = mapped_column(Text)
    logo_filename: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[Optional[str]] = mapped_column(String)

    conference: Mapped[Optional[Conference]] = relationship("Conference", back_populates="teams")
    airport: Mapped[Optional[Airport]] = relationship("Airport", primaryjoin="Team.airport_code==Airport.iata_code", viewonly=True)
    scorecard: Mapped[Optional[ScorecardSchool]] = relationship(
        "ScorecardSchool",
        primaryjoin="Team.scorecard_unitid==ScorecardSchool.unitid",
        viewonly=True,
    )
    players: Mapped[List["Player"]] = relationship("Player", back_populates="team", cascade="all, delete-orphan")

    coaches: Mapped[List["Coach"]] = relationship(
        "Coach",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    @property
    def aliases(self) -> List[str]:
        if not self.aliases_json:
            return []
        try:
            data = json.loads(self.aliases_json)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return []

    @property
    def niche(self) -> Optional[dict]:
        if not self.niche_json:
            return None
        try:
            data = json.loads(self.niche_json)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return None

class Coach(Base):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    title: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    phone: Mapped[Optional[str]] = mapped_column(String)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)

    team: Mapped[Team] = relationship("Team", back_populates="coaches")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("team_id", "name", "season", name="uq_player_team_season"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    position: Mapped[Optional[str]] = mapped_column(String)
    class_year: Mapped[Optional[str]] = mapped_column(String)
    height_inches: Mapped[Optional[int]] = mapped_column(Integer)
    season: Mapped[int] = mapped_column(Integer)

    team: Mapped[Team] = relationship("Team", back_populates="players")
    stats: Mapped[List["PlayerStats"]] = relationship(
        "PlayerStats",
        back_populates="player",
        cascade="all, delete-orphan",
    )


class PlayerStats(Base):
    __tablename__ = "player_stats"
    __table_args__ = (UniqueConstraint("player_id", "season", name="uq_player_stats"),)

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    ms: Mapped[Optional[float]] = mapped_column(Float)
    mp: Mapped[Optional[float]] = mapped_column(Float)
    sp: Mapped[Optional[float]] = mapped_column(Float)
    pts: Mapped[Optional[float]] = mapped_column(Float)
    pts_per_set: Mapped[Optional[float]] = mapped_column(Float)
    k: Mapped[Optional[float]] = mapped_column(Float)
    k_per_set: Mapped[Optional[float]] = mapped_column(Float)
    ae: Mapped[Optional[float]] = mapped_column(Float)
    ta: Mapped[Optional[float]] = mapped_column(Float)
    hit_pct: Mapped[Optional[float]] = mapped_column(Float)
    assists: Mapped[Optional[float]] = mapped_column(Float)
    assists_per_set: Mapped[Optional[float]] = mapped_column(Float)
    sa: Mapped[Optional[float]] = mapped_column(Float)
    sa_per_set: Mapped[Optional[float]] = mapped_column(Float)
    se: Mapped[Optional[float]] = mapped_column(Float)
    digs: Mapped[Optional[float]] = mapped_column(Float)
    digs_per_set: Mapped[Optional[float]] = mapped_column(Float)
    re: Mapped[Optional[float]] = mapped_column(Float)
    tre: Mapped[Optional[float]] = mapped_column(Float)
    rec_pct: Mapped[Optional[float]] = mapped_column(Float)
    bs: Mapped[Optional[float]] = mapped_column(Float)
    ba: Mapped[Optional[float]] = mapped_column(Float)
    tb: Mapped[Optional[float]] = mapped_column(Float)
    blocks_per_set: Mapped[Optional[float]] = mapped_column(Float)
    bhe: Mapped[Optional[float]] = mapped_column(Float)

    player: Mapped[Player] = relationship("Player", back_populates="stats")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[Optional[str]] = mapped_column(String)
    finished_at: Mapped[Optional[str]] = mapped_column(String)
    season: Mapped[Optional[int]] = mapped_column(Integer)
    rosters_path: Mapped[Optional[str]] = mapped_column(String)
    teams_path: Mapped[Optional[str]] = mapped_column(String)
    airports_path: Mapped[Optional[str]] = mapped_column(String)
    scorecard_path: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)
