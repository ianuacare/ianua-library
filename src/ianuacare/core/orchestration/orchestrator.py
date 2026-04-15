"""Model selection and inference execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, OrchestrationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import DataParser
from ianuacare.infrastructure.cache import CacheClient


class Orchestrator:
    """Parses input, selects a model, runs inference, and fills the packet."""

    def __init__(
        self,
        parser: DataParser,
        models: dict[str, BaseAIModel],
        *,
        default_model_key: str | None = None,
        cache: CacheClient | None = None,
        cache_ttl_seconds: int | None = 300,
    ) -> None:
        self._parser = parser
        self._models = dict[str, BaseAIModel](models)
        self._default_model_key = default_model_key
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    def execute(self, packet: DataPacket, context: RequestContext) -> DataPacket:
        """Parse, select model, run inference, and set ``processed_data`` / ``inference_result``."""
        model_key = self._select_model(context, packet)
        if model_key not in self._models:
            raise OrchestrationError(f"Unknown model key: {model_key}")
        self._parser.parse(packet, model_key=model_key)
        model = self._models[model_key]
        payload = packet.parsed_data
        cache_key = self._build_cache_key(model_key=model_key, payload=payload)
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                packet.processed_data = self._normalize_processed(cached)
                packet.inference_result = cached
                return packet
        try:
            result = model.run(payload)
        except Exception as exc:
            raise InferenceError("Model inference failed") from exc
        if self._cache is not None:
            self._cache.set(cache_key, result, ttl_seconds=self._cache_ttl_seconds)
        packet.processed_data = self._normalize_processed(result)
        packet.inference_result = result
        return packet

    def _select_model(self, context: RequestContext, packet: DataPacket) -> str:
        """Resolve model key from context metadata or default."""
        meta = context.metadata
        key = meta.get("model_key") or packet.metadata.get("model_key")
        if isinstance(key, str) and key in self._models:
            return key
        if self._default_model_key and self._default_model_key in self._models:
            return self._default_model_key
        if len(self._models) == 1:
            return next(iter(self._models))
        raise OrchestrationError("Could not select a model for this request")

    @staticmethod
    def _normalize_processed(result: Any) -> Any:
        """Normalize model output for storage layer."""
        if isinstance(result, dict):
            return dict(result)
        return {"output": result}

    @staticmethod
    def _build_cache_key(*, model_key: str, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{model_key}:{serialized}".encode()).hexdigest()
        return f"orchestrator:{digest}"

