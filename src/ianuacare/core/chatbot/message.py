"""Typed messages and retrieved vector points for the chatbot layer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "system", "tool"]


@dataclass(slots=True)
class Message:
    """Chat turn with explicit role."""

    role: Role
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return message


class ConversationMemory:
    """History and rolling summary for one conversation; no retrieval policy."""

    def __init__(self, *, system_prompt: str | None = None) -> None:
        self.summary = ""
        self.turn_index = 0
        self.context: list[Message] = []
        if system_prompt:
            self.context.append(Message(role="system", content=system_prompt))

    def total_chars(self) -> int:
        return sum(
            len(m.content) + (len(json.dumps(m.tool_calls)) if m.tool_calls else 0)
            for m in self.context
        )

    def append_turn(self, user_content: str, assistant_content: str) -> None:
        self.context.extend(
            [
                Message(role="user", content=user_content),
                Message(role="assistant", content=assistant_content),
            ]
        )
        self.turn_index += 1

    def summary_payload(self, history: list[Message] | None = None) -> dict[str, Any]:
        return {
            "task": "summarize",
            "previous_summary": self.summary,
            "history": [m.to_dict() for m in (self.context if history is None else history)],
        }

    def replace_with_summary(self, summary: str) -> None:
        self.summary = summary
        self.context = [m for m in self.context if m.role == "system"]


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
        raw_payload = hit.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else {}
        text = str(payload.get("source_text") or "")
        raw_id = hit.get("id")
        if raw_id is not None and str(raw_id).strip():
            pid = str(raw_id)
        else:
            pid = hashlib.sha256(text.encode()).hexdigest()[:32]
        score = float(hit.get("score") or 0.0)
        return cls(id=pid, source_text=text, score=score, turn=turn)
