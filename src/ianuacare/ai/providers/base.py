"""Base abstractions for AI providers."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any


class AIProvider(ABC):
    """Common contract for provider-side inference."""

    @abstractmethod
    def infer(self, model_name: str, payload: Any) -> Any:
        """Return raw backend output for ``model_name`` and ``payload``."""
        ...

    def infer_stream(self, model_name: str, payload: Any) -> Iterator[str]:
        """Stream text chunks for ``model_name``; default wraps a single ``infer`` call."""
        raw = self.infer(model_name, payload)
        text = self._raw_to_stream_text(raw)
        if text:
            yield text

    async def ainfer(self, model_name: str, payload: Any) -> Any:
        """Async inference; default runs ``infer`` in a thread."""
        return await asyncio.to_thread(self.infer, model_name, payload)

    async def ainfer_stream(self, model_name: str, payload: Any) -> AsyncIterator[str]:
        """Async text stream; default materializes ``infer_stream`` in a worker thread."""
        chunks: list[str] = await asyncio.to_thread(
            lambda: list(self.infer_stream(model_name, payload))
        )
        for chunk in chunks:
            yield chunk

    @staticmethod
    def _raw_to_stream_text(raw: Any) -> str:
        """Extract assistant-visible text from a provider ``infer`` payload."""
        if isinstance(raw, dict):
            content = raw.get("content")
            if content is not None:
                return str(content)
            text = raw.get("text")
            if text is not None:
                return str(text)
            summary = raw.get("summary")
            if summary is not None:
                return str(summary)
        return str(raw) if raw is not None else ""
