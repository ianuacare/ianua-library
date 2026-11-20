"""Model selection and inference execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, OrchestrationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.infrastructure.cache import CacheClient


class Orchestrator:
    """Parses input, selects a model, runs inference, and parses the output."""

    def __init__(
        self,
        input_parser: InputDataParser,
        output_parser: OutputDataParser,
        models: dict[str, BaseAIModel],
        *,
        default_model_key: str | None = None,
        cache: CacheClient | None = None,
        cache_ttl_seconds: int | None = 300,
    ) -> None:
        self._input_parser = input_parser
        self._output_parser = output_parser
        self._models = dict[str, BaseAIModel](models)
        self._default_model_key = default_model_key
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    def embed_text(self, text: str, context: RequestContext) -> list[float]:
        """Run ``text_embedder`` on ``text`` and return the top-level vector.

        Input is prepared via :meth:`InputDataParser` (including token-based
        chunking). The returned vector is ``text_vect``, the mean of chunk
        embeddings.
        """
        _ = context  # kept for symmetry with other orchestration entrypoints
        if "text_embedder" not in self._models:
            raise OrchestrationError("text_embedder model is not registered")
        if not isinstance(text, str) or not text.strip():
            raise OrchestrationError("text must be a non-empty string")
        packet = DataPacket(
            validated_data={
                "id_artefatto_trascrizione": "prompt",
                "text": text,
                "split_sentences": False,
                "split_words": False,
            }
        )
        self._input_parser.parse(packet, model_key="text_embedder")
        try:
            result = self._models["text_embedder"].run(packet.parsed_data)
        except Exception as exc:
            raise InferenceError("text_embedder inference failed") from exc
        vector = result.get("text_vect") if isinstance(result, dict) else None
        if not isinstance(vector, list) or not vector:
            raise OrchestrationError("text_embedder returned an empty vector")
        return [float(component) for component in vector]

    def execute(self, packet: DataPacket, context: RequestContext) -> DataPacket:
        """Run inference and parse the output with the request's validation options.

        ``context.metadata`` accepts a JSON schema under ``output_schema`` or a
        Pydantic class under ``output_model``. With a Pydantic class, an optional
        ``output_transform`` runs on the decoded object before validation.
        """
        model_key = self._select_model(context, packet)
        if model_key not in self._models:
            raise OrchestrationError(f"Unknown model key: {model_key}")
        schema = self._extract_output_schema(context)
        output_model = context.metadata.get("output_model")
        if output_model is not None and (
            not isinstance(output_model, type) or not issubclass(output_model, BaseModel)
        ):
            raise OrchestrationError("context.metadata['output_model'] must be a Pydantic class")
        transform = context.metadata.get("output_transform")
        if transform is not None and not callable(transform):
            raise OrchestrationError("context.metadata['output_transform'] must be callable")
        if output_model is not None and schema is not None:
            raise OrchestrationError("Specify either output_schema or output_model")
        if transform is not None and output_model is None:
            raise OrchestrationError("output_transform requires output_model")

        self._input_parser.parse(packet, model_key=model_key)
        payload = packet.parsed_data
        cache_key = self._build_cache_key(model_key=model_key, payload=payload)
        cached = self._cache.get(cache_key) if self._cache is not None else None
        result = cached
        if cached is None:
            try:
                result = self._models[model_key].run(payload)
            except Exception as exc:
                raise InferenceError("Model inference failed") from exc
        packet.inference_result = result
        self._output_parser.parse(
            packet,
            model_key=model_key,
            schema=schema,
            output_model=output_model,
            transform=transform,
        )
        if self._cache is not None and cached is None:
            self._cache.set(cache_key, result, ttl_seconds=self._cache_ttl_seconds)
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
    def _extract_output_schema(context: RequestContext) -> Mapping[str, Any] | None:
        """Read ``output_schema`` from ``context.metadata`` when provided as a mapping."""
        schema = context.metadata.get("output_schema")
        if schema is None:
            return None
        if not isinstance(schema, Mapping):
            raise OrchestrationError("context.metadata['output_schema'] must be a mapping")
        return schema

    @staticmethod
    def _build_cache_key(*, model_key: str, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{model_key}:{serialized}".encode()).hexdigest()
        return f"orchestrator:{digest}"
