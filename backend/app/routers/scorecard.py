from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(prefix="/scorecard", tags=["scorecard"])


@router.get("/{unitid}", response_model=schemas.ScorecardResponse, summary="Fetch College Scorecard metrics")
def get_scorecard(unitid: int, db: Session = Depends(get_db)) -> schemas.ScorecardResponse:
    stmt = select(models.ScorecardSchool).where(models.ScorecardSchool.unitid == unitid)
    school = db.execute(stmt).scalar_one_or_none()
    if school is None:
        raise HTTPException(status_code=404, detail="Scorecard record not found")
    return schemas.ScorecardResponse(data=schemas.ScorecardSchool.model_validate(school))
