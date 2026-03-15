from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services import analytics_service

router = APIRouter()


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    return analytics_service.get_summary(db)


@router.get("/analytics/recent")
def analytics_recent(limit: int = 25, db: Session = Depends(get_db)):
    return {"calls": analytics_service.get_recent_calls(db, limit=limit)}
