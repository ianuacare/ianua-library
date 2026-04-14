"""Base abstractions for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Common contract for provider-side inference."""

    @abstractmethod
    def infer(self, model_name: str, payload: Any) -> Any:
        """Return raw backend output for ``model_name`` and ``payload``."""
        ...
