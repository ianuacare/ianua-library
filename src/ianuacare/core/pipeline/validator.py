"""Validate pipeline data."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Literal

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket

BucketContentType = Literal["audio", "text"]


class DataValidator:
    """Applies validation rules and sets ``validated_data`` on the packet."""

    def __init__(self, *, allow_none_raw: bool = False) -> None:
        self._allow_none_raw = allow_none_raw

    def validate(self, packet: DataPacket) -> DataPacket:
        """Validate ``packet.raw_data`` and assign ``packet.validated_data``."""
        if packet.raw_data is None and not self._allow_none_raw:
            raise ValidationError("raw_data is required")
        packet.validated_data = self._coerce_validated(packet.raw_data)
        return packet

    def _coerce_validated(self, raw: Any) -> Any:
        """Override in subclasses for schema-based validation."""
        return raw

    def validate_bucket_payload(
        self,
        value: Any,
        *,
        content_type: BucketContentType,
        operation: str,
    ) -> dict[str, Any]:
        """Validate payloads for bucket flows (audio or text artefacts).

        Operations mirror ``prepare_upload``, ``upload_direct``, and ``retrieve``.
        """
        if content_type == "audio":
            return self.validate_audio_payload(value, operation=operation)
        if content_type == "text":
            if not isinstance(value, dict):
                raise ValidationError("payload must be a mapping")
            if operation == "prepare_upload":
                return self._validate_text_prepare(value)
            if operation == "upload_direct":
                return self._validate_text_upload_direct(value)
            if operation == "retrieve":
                return self._validate_bucket_retrieve(value)
            raise ValidationError(f"Unsupported bucket operation: {operation}")
        raise ValidationError(f"Unsupported bucket content_type: {content_type}")

    def validate_audio_payload(self, value: Any, *, operation: str) -> dict[str, Any]:
        """Validate audio payloads for ``prepare_upload`` and ``retrieve`` operations."""
        if not isinstance(value, dict):
            raise ValidationError("payload must be a mapping")
        if operation == "prepare_upload":
            return self._validate_audio_prepare(value)
        if operation == "upload_direct":
            return self._validate_audio_upload_direct(value)
        if operation == "retrieve":
            return self._validate_bucket_retrieve(value)
        raise ValidationError(f"Unsupported audio operation: {operation}")

    def validate_vector_payload(self, value: Any, *, operation: str) -> dict[str, Any]:
        """Validate vector-store payloads for ``upsert`` / ``search`` / ``delete`` / ``scroll``."""
        if not isinstance(value, dict):
            raise ValidationError("payload must be a mapping")
        collection = value.get("collection")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")

        if operation == "upsert":
            return self._validate_vector_upsert(value)
        if operation == "search":
            return self._validate_vector_search(value)
        if operation == "delete":
            return self._validate_vector_delete(value)
        if operation == "scroll":
            return self._validate_vector_scroll(value)
        raise ValidationError(f"Unsupported vector operation: {operation}")

    @staticmethod
    def _validate_vector_upsert(payload: dict[str, Any]) -> dict[str, Any]:
        artefatti = payload.get("artefatti")
        vector_field = payload.get("vector_field")
        if not isinstance(artefatti, list) or not artefatti:
            raise ValidationError("artefatti must be a non-empty list")
        if vector_field not in {"text", "sentence", "words"}:
            raise ValidationError("vector_field must be 'text', 'sentence', or 'words'")
        return payload

    @staticmethod
    def _validate_vector_search(payload: dict[str, Any]) -> dict[str, Any]:
        filters = payload.get("filters")
        if not isinstance(filters, dict) or "level" not in filters:
            raise ValidationError("filters.level is required")
        if filters["level"] not in {"text", "sentence", "words"}:
            raise ValidationError(
                "filters.level must be 'text', 'sentence', or 'words'"
            )
        has_vector = isinstance(payload.get("vector"), list) and bool(payload.get("vector"))
        has_prompt = isinstance(payload.get("prompt"), str) and bool(payload.get("prompt"))
        if not has_vector and not has_prompt:
            raise ValidationError("vector or prompt is required for search")
        top_k = payload.get("top_k", 10)
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValidationError("top_k must be a positive integer")
        return payload

    @staticmethod
    def _validate_vector_delete(payload: dict[str, Any]) -> dict[str, Any]:
        ids = payload.get("ids")
        filters = payload.get("filters")
        if ids is None and not filters:
            raise ValidationError("vector delete requires 'ids' or 'filters'")
        if ids is not None and not isinstance(ids, list):
            raise ValidationError("ids must be a list when provided")
        if filters is not None and not isinstance(filters, dict):
            raise ValidationError("filters must be a mapping when provided")
        return payload

    @staticmethod
    def _validate_vector_scroll(payload: dict[str, Any]) -> dict[str, Any]:
        filters = payload.get("filters")
        if filters is not None and not isinstance(filters, dict):
            raise ValidationError("filters must be a mapping when provided")
        batch_size = payload.get("batch_size", 256)
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValidationError("batch_size must be a positive integer")
        with_vectors = payload.get("with_vectors", False)
        if not isinstance(with_vectors, bool):
            raise ValidationError("with_vectors must be a boolean when provided")
        with_payload = payload.get("with_payload", True)
        if not isinstance(with_payload, bool):
            raise ValidationError("with_payload must be a boolean when provided")
        return payload

    def _validate_audio_prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        collection = payload.get("collection")
        filename = payload.get("filename")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")
        if not isinstance(filename, str) or not filename:
            raise ValidationError("filename is required")
        ext = Path(filename).suffix.lower()
        mime = payload.get("mime_type")
        allowed = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".webm": "audio/webm"}
        allowed_mimes = frozenset(
            ("audio/wav", "audio/mpeg", "audio/webm", "audio/webm;codecs=opus")
        )
        if ext not in allowed:
            raise ValidationError("filename must have .wav or .mp3 extension or .webm")
        if mime is not None and mime not in allowed_mimes:
            raise ValidationError(
                "mime_type must be audio/wav, audio/mpeg, audio/webm, or audio/webm;codecs=opus"
            )
        return {
            **payload,
            "mime_type": str(mime or allowed[ext]),
        }

    def _validate_bucket_retrieve(self, payload: dict[str, Any]) -> dict[str, Any]:
        collection = payload.get("collection")
        lookup_field = payload.get("lookup_field")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")
        if not isinstance(lookup_field, str) or not lookup_field:
            raise ValidationError("lookup_field is required")
        if payload.get("lookup_value") is None:
            raise ValidationError("lookup_value is required")
        return payload

    def _validate_text_prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        collection = payload.get("collection")
        filename = payload.get("filename")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")
        if not isinstance(filename, str) or not filename:
            raise ValidationError("filename is required")
        ext = Path(filename).suffix.lower()
        allowed = {".txt": "text/plain", ".md": "text/markdown"}
        if ext not in allowed:
            raise ValidationError("filename must have .txt or .md extension")
        mime = payload.get("mime_type")
        if mime is not None and mime not in ("text/plain", "text/markdown"):
            raise ValidationError("mime_type must be text/plain or text/markdown")
        return {
            **payload,
            "mime_type": str(mime or allowed[ext]),
        }

    def _validate_text_upload_direct(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._validate_text_prepare(payload)
        content = payload.get("content")
        content_b64 = payload.get("content_base64")
        if isinstance(content, str):
            normalized["content"] = content.encode("utf-8")
            return normalized
        if isinstance(content, (bytes, bytearray)):
            normalized["content"] = bytes(content)
            return normalized
        if isinstance(content_b64, str) and content_b64:
            try:
                normalized["content"] = base64.b64decode(content_b64, validate=True)
            except Exception as exc:
                raise ValidationError("content_base64 is not valid base64") from exc
            return normalized
        raise ValidationError("content (str/bytes) or content_base64 is required for upload_direct")

    def _validate_audio_upload_direct(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._validate_audio_prepare(payload)
        content = payload.get("content")
        content_b64 = payload.get("content_base64")
        if isinstance(content, str):
            normalized["content"] = content.encode()
            return normalized
        if isinstance(content, (bytes, bytearray)):
            normalized["content"] = bytes(content)
            return normalized
        if isinstance(content_b64, str) and content_b64:
            try:
                normalized["content"] = base64.b64decode(content_b64, validate=True)
            except Exception as exc:
                raise ValidationError("content_base64 is not valid base64") from exc
            return normalized
        raise ValidationError("content (bytes) or content_base64 is required for upload_direct")

