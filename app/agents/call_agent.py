class CallAgent:
    def __init__(self) -> None:
        pass

    def build_prompt(self, transcript: list[dict]) -> str:
        lines = []
        for item in transcript:
            lines.append(f"{item['role']}: {item['text']}")
        return "\n".join(lines)
