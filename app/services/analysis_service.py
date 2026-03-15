from app.agents.analysis_agent import AnalysisAgent
from app.db import models
from app.db.database import SessionLocal


class AnalysisService:
    def __init__(self) -> None:
        self.agent = AnalysisAgent()

    def run_by_id(self, call_id: str) -> models.CallAnalysis | None:
        db = SessionLocal()
        try:
            call = db.query(models.Call).filter(models.Call.id == call_id).first()
            if not call:
                return None
            result = self.agent.analyze(call)
            analysis = models.CallAnalysis(**result, call_id=call.id)
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            return analysis
        finally:
            db.close()
