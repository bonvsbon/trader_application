"""AI provider port + Phase 1 placeholder.

Phase 2 adds Claude/OpenAI/local adapters with failover behind this port.
Critically, AI is advisory only — it is never a safety layer. Even a confident
AI "BUY" must pass the Risk Engine and the order chokepoint unchanged.
"""

from __future__ import annotations


class NullAIProvider:
    name = "null"

    def analyze(self, prompt: str, context: dict) -> dict:
        return {"summary": "AI analysis is disabled in Phase 1", "confidence": 0.0}
