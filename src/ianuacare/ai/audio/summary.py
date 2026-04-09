"""Summary generation from diarized segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SummaryResult:
    text: str
    key_points: list[str]


class SummaryGenerator:
    """Generates concise summary text from diarized segments."""

    def __init__(self, provider: Any | None = None, model_name: str = "summarizer") -> None:
        self._provider = provider
        self._model_name = model_name

    def generate(
        self,
        *,
        segments: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> SummaryResult:
        payload = {"segments": segments, "context": context or {}}
        if self._provider is None:
            key_points = self._fallback_points(segments)
            return SummaryResult(text="\n".join(key_points), key_points=key_points)

        response = self._provider.infer(self._model_name, payload)
        text = str(response.get("text") or "").strip()
        if text:
            key_points = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
            return SummaryResult(text=text, key_points=key_points[:6])
        key_points = self._fallback_points(segments)
        return SummaryResult(text="\n".join(key_points), key_points=key_points)

    @staticmethod
    def _fallback_points(segments: list[dict[str, Any]]) -> list[str]:
        if not segments:
            return ["No transcript content available."]
        preview = " ".join(str(s.get("text") or "").strip() for s in segments[:3]).strip()
        speakers = sorted(
            {
                int(s.get("speaker_id", 0))
                for s in segments
                if s.get("speaker_id") is not None
            }
        )
        return [
            f"Transcript includes {len(segments)} segments.",
            f"Detected speakers: {', '.join(f'speaker_{s + 1}' for s in speakers) or 'unknown'}.",
            f"Preview: {preview[:220]}",
        ]
