from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/conferences", tags=["conferences"])


@router.get("/", response_model=list[schemas.Conference], summary="List all conferences")
def list_conferences(db: Session = Depends(get_db)) -> list[schemas.Conference]:
    stmt = select(models.Conference).order_by(models.Conference.name)
    conferences = db.execute(stmt).scalars().all()
    return [schemas.Conference.model_validate(conf) for conf in conferences]
