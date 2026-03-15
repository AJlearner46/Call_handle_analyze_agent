from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import models


def get_summary(db: Session) -> dict:
    total_calls = db.query(models.Call).count()
    successful_calls = db.query(models.Call).filter(models.Call.status == "completed").count()
    failed_calls = total_calls - successful_calls

    completed_calls = db.query(models.Call).filter(models.Call.end_time.isnot(None)).all()
    durations = [
        (call.end_time - call.start_time).total_seconds()
        for call in completed_calls
        if call.end_time and call.start_time
    ]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    intents = (
        db.query(models.CallAnalysis.purpose, func.count(models.CallAnalysis.id))
        .group_by(models.CallAnalysis.purpose)
        .all()
    )
    intent_distribution = [{"intent": purpose, "count": count} for purpose, count in intents]

    failure_rows = (
        db.query(models.CallAnalysis.failure_reason, func.count(models.CallAnalysis.id))
        .filter(models.CallAnalysis.failure_reason.isnot(None))
        .group_by(models.CallAnalysis.failure_reason)
        .all()
    )
    failure_reasons = [{"reason": reason, "count": count} for reason, count in failure_rows]

    return {
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "avg_duration_seconds": avg_duration,
        "intent_distribution": intent_distribution,
        "failure_reasons": failure_reasons,
    }


def get_recent_calls(db: Session, limit: int = 25) -> list[dict]:
    calls = (
        db.query(models.Call)
        .order_by(models.Call.start_time.desc())
        .limit(limit)
        .all()
    )
    call_ids = [call.id for call in calls]
    analyses = (
        db.query(models.CallAnalysis)
        .filter(models.CallAnalysis.call_id.in_(call_ids))
        .all()
    )
    analysis_map = {analysis.call_id: analysis for analysis in analyses}

    results = []
    for call in calls:
        analysis = analysis_map.get(call.id)
        results.append(
            {
                "call_id": call.id,
                "phone_number": call.phone_number,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "status": call.status,
                "purpose": analysis.purpose if analysis else "unknown",
                "success": analysis.success if analysis else False,
            }
        )
    return results
