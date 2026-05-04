"""Input/output parsers for storage-oriented pipeline paths.

These parsers are intentionally distinct from the model-oriented
:class:`~ianuacare.core.orchestration.parser.InputDataParser` and
:class:`~ianuacare.core.orchestration.parser.OutputDataParser`: they normalize
data flowing **to** or **from** PostgreSQL, S3 buckets, and Qdrant rather than
preparing model payloads.

Three concrete behaviors are provided:

- **CRUD**: caller-supplied schemas (``payload["schema"]``) project and coerce
  records on write; reads can be enriched via custom subclasses.
- **Bucket**: audio uploads can be chunked client-side; reads can recompose
  chunks (for ``upload_direct`` flows that produced multiple parts).
- **Qdrant**: write-side shaping forwards payload preparation to the
  ``Writer.write_vector_upsert`` artefact contract; read-side hooks normalize
  search/scroll results.

A pass-through pair is exposed for callers that do not need any of the above.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket

StorageChannel = Literal["crud", "vector", "audio", "bucket"]

# Default chunk size for audio uploads (bytes). Splitting happens only when the
# caller passes ``chunk_size`` in the bucket payload; otherwise the body stays
# whole.
DEFAULT_AUDIO_CHUNK_BYTES = 5 * 1024 * 1024


_JSON_TO_PYTHON: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list, tuple),
    "null": (type(None),),
}


def _coerce_value(value: Any, json_type: str) -> Any:
    """Best-effort coercion to a JSON Schema scalar type.

    Returns the value unchanged when no coercion rule applies; raises
    :class:`ValidationError` when coercion is unsafe (e.g. non-numeric string
    declared as ``integer``).
    """
    if value is None:
        return None
    expected = _JSON_TO_PYTHON.get(json_type)
    if expected is None:
        raise ValidationError(f"Unsupported schema type: {json_type}")
    if json_type in {"integer", "number"} and isinstance(value, bool):
        raise ValidationError(
            f"boolean is not a valid {json_type}; got {value!r}"
        )
    if isinstance(value, expected):
        return value
    try:
        if json_type == "string":
            return str(value)
        if json_type == "integer":
            return int(value)
        if json_type == "number":
            return float(value)
        if json_type == "boolean":
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes"}:
                    return True
                if lowered in {"false", "0", "no"}:
                    return False
            raise ValueError("not a boolean")
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"value {value!r} cannot be coerced to {json_type}"
        ) from exc
    return value


class StorageInputParser:
    """Hook invoked before write/update/delete on a storage backend."""

    def prepare_for_persist(
        self,
        packet: DataPacket,
        *,
        channel: StorageChannel,
        operation: str,
        context: RequestContext,
    ) -> None:
        """Dispatch to per-channel hooks; default implementation is no-op."""
        if channel == "crud":
            self._prepare_crud(packet, operation=operation, context=context)
        elif channel in {"audio", "bucket"}:
            self._prepare_bucket(packet, operation=operation, context=context)
        elif channel == "vector":
            self._prepare_vector(packet, operation=operation, context=context)

    def _prepare_crud(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = context
        if operation not in {"create", "update"}:
            return
        validated = packet.validated_data
        if not isinstance(validated, dict):
            return
        schema = validated.get("schema")
        if not isinstance(schema, dict):
            return
        properties = schema.get("properties")
        required = schema.get("required") or []
        if not isinstance(properties, dict):
            return
        target_key = "record" if operation == "create" else "updates"
        record = validated.get(target_key)
        if not isinstance(record, dict):
            return
        projected: dict[str, Any] = {}
        for name, prop_schema in properties.items():
            if name not in record:
                continue
            json_type = (
                prop_schema.get("type") if isinstance(prop_schema, dict) else None
            )
            projected[name] = (
                _coerce_value(record[name], json_type)
                if isinstance(json_type, str)
                else record[name]
            )
        if operation == "create":
            missing = [
                field for field in required
                if isinstance(field, str) and field not in projected
            ]
            if missing:
                raise ValidationError(
                    "missing required fields: " + ", ".join(missing)
                )
        validated[target_key] = projected
        packet.parsed_data = projected

    def _prepare_bucket(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = context
        if operation != "upload_direct":
            return
        validated = packet.validated_data
        if not isinstance(validated, dict):
            return
        chunk_size = validated.get("chunk_size")
        content = validated.get("content")
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            return
        if not isinstance(content, (bytes, bytearray)):
            return
        chunks = list(_split_bytes(bytes(content), chunk_size))
        validated["chunks"] = chunks
        packet.parsed_data = {"chunks": chunks, "chunk_count": len(chunks)}

    def _prepare_vector(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = context
        if operation != "upsert":
            return
        validated = packet.validated_data
        if not isinstance(validated, dict):
            return
        artefatti = validated.get("artefatti")
        if not isinstance(artefatti, list):
            return
        normalized: list[dict[str, Any]] = []
        for index, artefact in enumerate(artefatti):
            if not isinstance(artefact, dict):
                raise ValidationError(
                    f"vector artefact at index {index} must be a mapping"
                )
            payload = {k: v for k, v in artefact.items() if v is not None}
            normalized.append(payload)
        validated["artefatti"] = normalized
        packet.parsed_data = {"artefatti": normalized}


class StorageOutputParser:
    """Hook invoked after a storage read fills ``packet.processed_data``."""

    def after_read(
        self,
        packet: DataPacket,
        *,
        channel: StorageChannel,
        operation: str,
        context: RequestContext,
    ) -> None:
        """Dispatch to per-channel hooks; default implementation normalizes types."""
        if channel == "crud":
            self._after_crud(packet, operation=operation, context=context)
        elif channel in {"audio", "bucket"}:
            self._after_bucket(packet, operation=operation, context=context)
        elif channel == "vector":
            self._after_vector(packet, operation=operation, context=context)

    def _after_crud(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = operation, context
        # Trim known internal-only keys from outgoing read records when they
        # exist, without touching the underlying value semantics.
        result = packet.processed_data
        if isinstance(result, dict):
            packet.processed_data = {k: v for k, v in result.items() if k != "_internal"}
        elif isinstance(result, list):
            packet.processed_data = [
                {k: v for k, v in item.items() if k != "_internal"}
                if isinstance(item, dict)
                else item
                for item in result
            ]

    def _after_bucket(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = context
        if operation != "retrieve":
            return
        record = packet.processed_data
        if not isinstance(record, dict):
            return
        chunks = record.get("chunks")
        if isinstance(chunks, list) and all(
            isinstance(c, (bytes, bytearray)) for c in chunks
        ):
            recomposed = b"".join(bytes(c) for c in chunks)
            packet.processed_data = {**record, "content": recomposed}

    def _after_vector(
        self,
        packet: DataPacket,
        *,
        operation: str,
        context: RequestContext,
    ) -> None:
        _ = context
        if operation not in {"search", "scroll"}:
            return
        result = packet.processed_data
        if not isinstance(result, list):
            return
        packet.processed_data = [
            self._normalize_vector_point(point) for point in result
        ]

    @staticmethod
    def _normalize_vector_point(point: Any) -> Any:
        if not isinstance(point, dict):
            return point
        normalized = dict(point)
        payload = normalized.get("payload")
        if isinstance(payload, dict):
            normalized["payload"] = dict(payload)
        return normalized


def _split_bytes(body: bytes, chunk_size: int) -> Iterable[bytes]:
    for start in range(0, len(body), chunk_size):
        yield body[start : start + chunk_size]


class PassthroughStorageInputParser(StorageInputParser):
    """Default storage input parser; behavior matches :class:`StorageInputParser`."""


class PassthroughStorageOutputParser(StorageOutputParser):
    """Default storage output parser; behavior matches :class:`StorageOutputParser`."""
