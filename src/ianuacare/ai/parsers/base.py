"""Base parser interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """Abstract parser contract."""

    @abstractmethod
    def parse(self, data: Any) -> Any:
        ...
