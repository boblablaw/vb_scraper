from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, noload, selectinload

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/players", tags=["players"])


STAT_FIELDS = {
    "ms",
    "mp",
    "sp",
    "pts",
    "pts_per_set",
    "k",
    "k_per_set",
    "ae",
    "ta",
    "hit_pct",
    "assists",
    "assists_per_set",
    "sa",
    "sa_per_set",
    "se",
    "digs",
    "digs_per_set",
    "re",
    "tre",
    "rec_pct",
    "bs",
    "ba",
    "tb",
    "blocks_per_set",
    "bhe",
}


@router.get("/", response_model=schemas.PlayerList, summary="List players with optional filters")
def list_players(
    team_id: int | None = Query(None),
    season: int | None = Query(None),
    position: str | None = Query(None),
    class_year: str | None = Query(None),
    search: str | None = Query(None, description="Partial case-insensitive name match"),
    include_stats: bool = Query(False, description="Include per-player stat rows"),
    sort_field: str | None = Query(
        None,
        description="Sort field key (e.g. 'conference', 'team', 'name', 'pts')",
        alias="sort_field",
    ),
    sort_dir: str = Query(
        "asc",
        description="Sort direction: 'asc' or 'desc'",
        alias="sort_dir",
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.PlayerList:
    filters = []
    if team_id:
        filters.append(models.Player.team_id == team_id)
    if season:
        filters.append(models.Player.season == season)
    if position:
        filters.append(func.lower(models.Player.position) == position.lower())
    if class_year:
        filters.append(func.lower(models.Player.class_year) == class_year.lower())
    if search:
        pattern = f"%{search.lower()}%"
        filters.append(func.lower(models.Player.name).like(pattern))

    # Normalise sort direction.
    sort_dir = (sort_dir or "asc").lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"

    base_stmt = (
        select(models.Player)
        .join(models.Team, models.Player.team_id == models.Team.id)
        .join(
            models.Conference,
            models.Team.conference_id == models.Conference.id,
            isouter=True,
        )
        .join(
            models.PlayerStats,
            (models.PlayerStats.player_id == models.Player.id)
            & (models.PlayerStats.season == season),
            isouter=True,
        )
        .where(*filters)
    )
    total = db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    ).scalar_one()

    options = [selectinload(models.Player.team)]
    if include_stats:
        options.append(selectinload(models.Player.stats))
    else:
        options.append(noload(models.Player.stats))

    # Build server-side order_by based on requested sort_field.
    order_columns = []
    dir_fn = lambda col: col.desc() if sort_dir == "desc" else col.asc()

    if sort_field == "conference":
        primary = models.Conference.name
        order_columns.extend(
            [
                dir_fn(primary),
                models.Team.name.asc(),
                models.Player.name.asc(),
            ]
        )
    elif sort_field == "team":
        primary = models.Team.name
        order_columns.extend(
            [
                models.Conference.name.asc(),
                dir_fn(primary),
                models.Player.name.asc(),
            ]
        )
    elif sort_field == "name":
        primary = models.Player.name
        order_columns.extend(
            [
                models.Conference.name.asc(),
                models.Team.name.asc(),
                dir_fn(primary),
            ]
        )
    elif sort_field in STAT_FIELDS:
        stat_col = getattr(models.PlayerStats, sort_field)
        order_columns.extend(
            [
                dir_fn(stat_col),
                models.Conference.name.asc(),
                models.Team.name.asc(),
                models.Player.name.asc(),
            ]
        )
    else:
        # Default sort: conference > team > name.
        order_columns.extend(
            [
                models.Conference.name.asc(),
                models.Team.name.asc(),
                models.Player.name.asc(),
            ]
        )

    stmt = (
        base_stmt.options(*options)
        .order_by(*order_columns)
        .offset(offset)
        .limit(limit)
    )
    players = db.execute(stmt).scalars().all()

    return schemas.PlayerList(
        results=[schemas.Player.model_validate(player) for player in players],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{player_id}", response_model=schemas.Player, summary="Fetch a single player row")
def get_player(
    player_id: int,
    include_stats: bool = Query(True, description="Include per-player stat row"),
    db: Session = Depends(get_db),
) -> schemas.Player:
    options = [selectinload(models.Player.team)]
    if include_stats:
        options.append(selectinload(models.Player.stats))
    else:
        options.append(noload(models.Player.stats))

    stmt = select(models.Player).options(*options).where(models.Player.id == player_id)
    player = db.execute(stmt).scalar_one_or_none()
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    return schemas.Player.model_validate(player)
