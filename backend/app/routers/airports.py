from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/airports", tags=["airports"])


@router.get("/", response_model=schemas.AirportList, summary="List airports referenced by teams")
def list_airports(
    state: str | None = Query(None, description="Filter by ISO region code (e.g., US-CA)"),
    search: str | None = Query(None, description="Search by airport or city name"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> schemas.AirportList:
    stmt = select(models.Airport)
    if state:
        stmt = stmt.where(func.lower(models.Airport.iso_region) == state.lower())
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(models.Airport.name).like(pattern)
            | func.lower(models.Airport.municipality).like(pattern)
            | func.lower(models.Airport.iata_code).like(pattern)
        )
    stmt = stmt.order_by(models.Airport.name).limit(limit)
    airports = db.execute(stmt).scalars().all()
    return schemas.AirportList(results=[schemas.Airport.model_validate(a) for a in airports])
