from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/", response_model=schemas.TeamList, summary="List teams with optional filters")
def list_teams(
    conference: str | None = Query(None, description="Filter by conference name"),
    state: str | None = Query(None, description="Filter by state/territory code"),
    tier: str | None = Query(None, description="Filter by internal tier label"),
    search: str | None = Query(None, description="Full/partial match on team or short name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.TeamList:
    filters = []
    if conference:
        filters.append(
            models.Team.conference.has(
                func.lower(models.Conference.name) == conference.lower()
            )
        )
    if state:
        filters.append(func.lower(models.Team.state) == state.lower())
    if tier:
        filters.append(func.lower(models.Team.tier) == tier.lower())
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(models.Team.name).like(pattern),
                func.lower(models.Team.short_name).like(pattern),
            )
        )

    base_stmt = select(models.Team).where(*filters)
    total = db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    ).scalar_one()

    stmt = (
        base_stmt.options(
            selectinload(models.Team.conference),
            selectinload(models.Team.airport),
            selectinload(models.Team.scorecard),
        )
        .order_by(models.Team.name)
        .offset(offset)
        .limit(limit)
    )
    teams = db.execute(stmt).scalars().all()

    return schemas.TeamList(
        results=[schemas.TeamSummary.model_validate(team) for team in teams],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{team_id}", response_model=schemas.TeamDetailResponse, summary="Get a single team's metadata")
def get_team(team_id: int, db: Session = Depends(get_db)) -> schemas.TeamDetailResponse:
    stmt = (
        select(models.Team)
        .options(
            selectinload(models.Team.conference),
            selectinload(models.Team.airport),
            selectinload(models.Team.scorecard),
            selectinload(models.Team.coaches),
        )
        .where(models.Team.id == team_id)
    )
    team = db.execute(stmt).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    data = schemas.TeamDetail.model_validate(team)
    return schemas.TeamDetailResponse(data=data)
