"""Validate pipeline data."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket


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

    def validate_audio_payload(self, value: Any, *, operation: str) -> dict[str, Any]:
        """Validate audio payloads for ``prepare_upload`` and ``retrieve`` operations."""
        if not isinstance(value, dict):
            raise ValidationError("payload must be a mapping")
        if operation == "prepare_upload":
            return self._validate_audio_prepare(value)
        if operation == "upload_direct":
            return self._validate_audio_upload_direct(value)
        if operation == "retrieve":
            return self._validate_audio_retrieve(value)
        raise ValidationError(f"Unsupported audio operation: {operation}")

    def _validate_audio_prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        collection = payload.get("collection")
        filename = payload.get("filename")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")
        if not isinstance(filename, str) or not filename:
            raise ValidationError("filename is required")
        ext = Path(filename).suffix.lower()
        mime = payload.get("mime_type")
        allowed = {".wav": "audio/wav", ".mp3": "audio/mpeg"}
        if ext not in allowed:
            raise ValidationError("filename must have .wav or .mp3 extension")
        if mime is not None and mime not in ("audio/wav", "audio/mpeg"):
            raise ValidationError("mime_type must be audio/wav or audio/mpeg")
        return {
            **payload,
            "mime_type": str(mime or allowed[ext]),
        }

    def _validate_audio_retrieve(self, payload: dict[str, Any]) -> dict[str, Any]:
        collection = payload.get("collection")
        lookup_field = payload.get("lookup_field")
        if not isinstance(collection, str) or not collection:
            raise ValidationError("collection is required")
        if not isinstance(lookup_field, str) or not lookup_field:
            raise ValidationError("lookup_field is required")
        if payload.get("lookup_value") is None:
            raise ValidationError("lookup_value is required")
        return payload

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

