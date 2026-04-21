"""Base abstractions for AI providers."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any


class AIProvider(ABC):
    """Common contract for provider-side inference."""

    @abstractmethod
    def infer(self, model_name: str, payload: Any, *, model_type: str | None = None) -> Any:
        """Return raw backend output for ``model_name`` and ``payload``.

        ``model_type`` hints the backend modality (for example ``"embedding"`` vs chat);
        providers that only support one mode may ignore it.
        """
        ...

    def infer_stream(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> Iterator[str]:
        """Stream text chunks for ``model_name``; default wraps a single ``infer`` call."""
        raw = self.infer(model_name, payload, model_type=model_type)
        text = self._raw_to_stream_text(raw)
        if text:
            yield text

    async def ainfer(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> Any:
        """Async inference; default runs ``infer`` in a thread."""
        return await asyncio.to_thread(self.infer, model_name, payload, model_type=model_type)

    async def ainfer_stream(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> AsyncIterator[str]:
        """Async text stream; default materializes ``infer_stream`` in a worker thread."""
        chunks: list[str] = await asyncio.to_thread(
            lambda: list(self.infer_stream(model_name, payload, model_type=model_type))
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
