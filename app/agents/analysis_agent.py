from app.services.llm_service import LLMService


class AnalysisAgent:
    def __init__(self) -> None:
        self.llm = None
        try:
            self.llm = LLMService()
        except RuntimeError:
            self.llm = None

    def analyze(self, call) -> dict:
        context = call.context or {}
        purpose = context.get("intent", "unknown")
        success = call.status == "completed"
        failure_reason = None if success else "call ended before completion"
        improvement = "Offer fewer options and confirm details before ending the call."

        if not self.llm:
            return {
                "purpose": purpose,
                "success": success,
                "failure_reason": failure_reason,
                "improvement": improvement,
            }

        transcript_lines = []
        for item in call.transcript or []:
            transcript_lines.append(f"{item.get('role')}: {item.get('text')}")
        transcript_text = "\n".join(transcript_lines)

        prompt = (
            "Analyze this healthcare call transcript. Return strict JSON with keys: "
            "purpose, success, failure_reason, improvement. "
            f"Call status: {call.status}. "
            f"Transcript:\n{transcript_text}"
        )
        result = self.llm.generate_json(prompt, fallback={})
        return {
            "purpose": result.get("purpose", purpose),
            "success": bool(result.get("success", success)),
            "failure_reason": result.get("failure_reason", failure_reason),
            "improvement": result.get("improvement", improvement),
        }
