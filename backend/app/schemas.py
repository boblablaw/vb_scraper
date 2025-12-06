from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Conference(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class Airport(BaseModel):
    name: Optional[str]
    iata_code: Optional[str]
    municipality: Optional[str]
    iso_region: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    score: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class ScorecardSchool(BaseModel):
    unitid: int
    instnm: Optional[str]
    city: Optional[str]
    state: Optional[str]
    adm_rate: Optional[float]
    sat_avg: Optional[float]
    tuition_in: Optional[float]
    tuition_out: Optional[float]
    cost_t4: Optional[float]
    grad_rate: Optional[float]
    retention_rate: Optional[float]
    pct_pell: Optional[float]
    pct_fulltime_fac: Optional[float]
    median_earnings: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class TeamSummary(BaseModel):
    id: int
    name: str
    short_name: Optional[str]
    city: Optional[str]
    state: Optional[str]
    tier: Optional[str]
    conference: Optional[Conference]
    airport_code: Optional[str]
    scorecard_unitid: Optional[int]
    logo_filename: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TeamDetail(TeamSummary):
    url: Optional[str]
    stats_url: Optional[str]
    political_label: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    airport_name: Optional[str]
    airport_drive_time: Optional[str]
    airport_notes: Optional[str]
    notes: Optional[str]
    risk_watchouts: Optional[str]
    scorecard_confidence: Optional[str]
    scorecard_match_name: Optional[str]
    aliases: List[str] = Field(default_factory=list)
    niche: Optional[dict[str, Any]] = None
    airport: Optional[Airport] = None
    scorecard: Optional[ScorecardSchool] = None
    coaches: List["Coach"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TeamList(BaseModel):
    results: List[TeamSummary]
    total: int
    limit: int
    offset: int


class TeamDetailResponse(BaseModel):
    data: TeamDetail


class TeamRef(BaseModel):
    id: int
    name: str
    short_name: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class Coach(BaseModel):
    id: int
    name: str
    title: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    sort_order: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class PlayerStats(BaseModel):
    season: int
    ms: Optional[float]
    mp: Optional[float]
    sp: Optional[float]
    pts: Optional[float]
    pts_per_set: Optional[float]
    k: Optional[float]
    k_per_set: Optional[float]
    ae: Optional[float]
    ta: Optional[float]
    hit_pct: Optional[float]
    assists: Optional[float]
    assists_per_set: Optional[float]
    sa: Optional[float]
    sa_per_set: Optional[float]
    se: Optional[float]
    digs: Optional[float]
    digs_per_set: Optional[float]
    re: Optional[float]
    tre: Optional[float]
    rec_pct: Optional[float]
    bs: Optional[float]
    ba: Optional[float]
    tb: Optional[float]
    blocks_per_set: Optional[float]
    bhe: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class Player(BaseModel):
    id: int
    name: str
    position: Optional[str]
    class_year: Optional[str]
    height_inches: Optional[int]
    season: int
    team: TeamRef
    stats: List[PlayerStats] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PlayerList(BaseModel):
    results: List[Player]
    total: int
    limit: int
    offset: int


class AirportList(BaseModel):
    results: List[Airport]


class ScorecardResponse(BaseModel):
    data: ScorecardSchool
