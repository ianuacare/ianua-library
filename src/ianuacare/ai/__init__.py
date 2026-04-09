"""AI models and providers."""

from ianuacare.ai.base import BaseAIModel
from ianuacare.ai.nlp.model import NLPModel
from ianuacare.ai.provider import AIProvider

from . import audio

try:  # Optional dependency: together
    from ianuacare.ai.providers import TogetherAIProvider
except Exception:  # pragma: no cover - import-time optional dependency handling
    TogetherAIProvider = None  # type: ignore[assignment]

__all__ = ["AIProvider", "BaseAIModel", "NLPModel", "TogetherAIProvider", "audio"]
