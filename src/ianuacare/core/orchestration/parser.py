"""Input and output data parsers for the orchestration stage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket


class InputDataParser:
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


_JSON_SCHEMA_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list, tuple),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


class OutputDataParser:
    """Transforms ``inference_result`` into ``processed_data``, branching by model key."""

    def parse(
        self,
        packet: DataPacket,
        *,
        model_key: str | None = None,
        schema: Mapping[str, Any] | None = None,
    ) -> DataPacket:
        """Validate (when applicable) and normalize the inference result."""
        result = packet.inference_result
        key = (model_key or "").strip().lower() if isinstance(model_key, str) else ""

        if key == "llm":
            result = self._parse_llm(result, schema=schema)
        elif key == "diarization":
            result = self._parse_diarization(result)

        packet.processed_data = self._normalize_processed(result)
        return packet

    def _parse_llm(self, result: Any, *, schema: Mapping[str, Any] | None) -> Any:
        """Branch for ``llm``: when a schema is provided, validate required fields and type coherence."""
        if schema is None:
            return result
        self._check_required_fields(result, schema)
        self._check_schema_coherence(result, schema)
        return result

    def _parse_diarization(self, result: Any) -> Any:
        """Branch for ``diarization``: placeholder for future post-processing hooks."""
        return result

    @staticmethod
    def _normalize_processed(result: Any) -> Any:
        """Normalize model output for storage layer."""
        if isinstance(result, dict):
            return dict(result)
        return {"output": result}

    @staticmethod
    def _check_required_fields(result: Any, schema: Mapping[str, Any]) -> None:
        """Ensure every key in ``schema['required']`` is present in the result mapping."""
        required = schema.get("required")
        if required is None:
            return
        if not isinstance(required, (list, tuple)):
            raise ValidationError("schema.required must be a list")
        if not isinstance(result, dict):
            raise ValidationError("llm output must be a mapping to check required fields")
        missing = [field for field in required if field not in result]
        if missing:
            raise ValidationError(
                f"llm output is missing required fields: {', '.join(map(str, missing))}"
            )

    @staticmethod
    def _check_schema_coherence(result: Any, schema: Mapping[str, Any]) -> None:
        """Validate top-level ``properties.<name>.type`` against actual Python types of the result."""
        properties = schema.get("properties")
        if properties is None:
            return
        if not isinstance(properties, Mapping):
            raise ValidationError("schema.properties must be a mapping")
        if not isinstance(result, dict):
            raise ValidationError("llm output must be a mapping to check schema coherence")
        for name, prop_schema in properties.items():
            if name not in result:
                continue
            if not isinstance(prop_schema, Mapping):
                continue
            expected_type = prop_schema.get("type")
            if expected_type is None:
                continue
            value = result[name]
            if not OutputDataParser._matches_json_type(value, expected_type):
                raise ValidationError(
                    f"llm output field '{name}' does not match expected type '{expected_type}'"
                )

    @staticmethod
    def _matches_json_type(value: Any, expected_type: Any) -> bool:
        """Check a value against a JSON Schema ``type`` declaration (string or list of strings)."""
        if isinstance(expected_type, list):
            return any(
                OutputDataParser._matches_json_type(value, single) for single in expected_type
            )
        if not isinstance(expected_type, str):
            raise ValidationError("schema property 'type' must be a string or list of strings")
        python_types = _JSON_SCHEMA_TYPE_MAP.get(expected_type)
        if python_types is None:
            raise ValidationError(f"Unsupported JSON schema type: {expected_type}")
        # Booleans are a subclass of int in Python; exclude them from integer/number matches.
        if expected_type in {"integer", "number"} and isinstance(value, bool):
            return False
        return isinstance(value, python_types)
