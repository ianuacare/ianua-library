"""Abstract base for AI models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAIModel(ABC):
    """Common model interface."""

    @abstractmethod
    def run(self, payload: Any) -> Any:
        """Run model inference over ``payload``."""
        ...
