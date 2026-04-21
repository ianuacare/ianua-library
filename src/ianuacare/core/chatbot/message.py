"""Typed messages and retrieved vector points for the chatbot layer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

Role = Literal["user", "assistant", "system"]


@dataclass(slots=True)
class Message:
    """Chat turn with explicit role."""

    role: Role
    content: str


@dataclass(slots=True)
class RetrievedPoint:
    """Single hit from vector search with metadata for cross-turn reranking."""

    id: str
    source_text: str
    score: float
    turn: int

    @classmethod
    def from_vector_hit(cls, hit: dict[str, Any], turn: int) -> RetrievedPoint:
        """Build from a ``Reader.read_vector_search`` row (id, score, payload)."""
        payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
        text = str(payload.get("source_text") or "")
        raw_id = hit.get("id")
        if raw_id is not None and str(raw_id).strip():
            pid = str(raw_id)
        else:
            pid = hashlib.sha256(text.encode()).hexdigest()[:32]
        score = float(hit.get("score") or 0.0)
        return cls(id=pid, source_text=text, score=score, turn=turn)
