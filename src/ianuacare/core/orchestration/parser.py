"""Parse validated input into structured ``parsed_data``."""

from __future__ import annotations

from typing import Any

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket


class DataParser:
    """Transforms ``validated_data`` into ``parsed_data`` (e.g. JSON, clinical text)."""

    def parse(self, packet: DataPacket, *, model_key: str | None = None) -> DataPacket:
        """Default: pass-through copy of ``validated_data``."""
        packet.parsed_data = self._parse_impl(packet.validated_data, model_key=model_key)
        return packet

    def _parse_impl(self, validated: Any, *, model_key: str | None = None) -> Any:
        """Prepare payload by model key before provider invocation."""
        if not isinstance(model_key, str):
            return validated

        key = model_key.strip().lower()
        if key == "llm":
            if not isinstance(validated, dict):
                raise ValidationError("validated_data must be a mapping for llm")
            text = validated.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValidationError("validated_data.text is required for llm")
            return {"prompt": "", "text": text}

        if key == "diarization":
            if not isinstance(validated, dict):
                raise ValidationError("validated_data must be a mapping for diarization")
            segments = validated.get("segments")
            if segments is None:
                segments = []
            if not isinstance(segments, list):
                raise ValidationError("validated_data.segments must be a list for diarization")
            payload = {"segments": segments}
            for field in ("audio_path", "num_speakers", "language", "response_format"):
                if field in validated:
                    payload[field] = validated[field]
            return payload

        return validated

