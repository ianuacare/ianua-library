"""Storage parsers: CRUD schema, bucket chunking, vector payload shaping."""

import pytest

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.models.user import User
from ianuacare.core.pipeline.storage_parsers import (
    StorageInputParser,
    StorageOutputParser,
)


def _ctx() -> RequestContext:
    return RequestContext(User("u1", "r", []), "prod", {})


def test_crud_input_projects_and_coerces_types() -> None:
    packet = DataPacket(
        validated_data={
            "collection": "patients",
            "schema": {
                "properties": {
                    "id": {"type": "string"},
                    "age": {"type": "integer"},
                    "active": {"type": "boolean"},
                },
                "required": ["id", "age"],
            },
            "record": {
                "id": "p1",
                "age": "42",
                "active": "true",
                "ignored": "drop me",
            },
        }
    )
    StorageInputParser().prepare_for_persist(
        packet, channel="crud", operation="create", context=_ctx()
    )
    assert packet.validated_data["record"] == {"id": "p1", "age": 42, "active": True}
    assert "ignored" not in packet.validated_data["record"]


def test_crud_input_missing_required_raises() -> None:
    packet = DataPacket(
        validated_data={
            "schema": {
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
            "record": {"name": "x"},
        }
    )
    with pytest.raises(ValidationError):
        StorageInputParser().prepare_for_persist(
            packet, channel="crud", operation="create", context=_ctx()
        )


def test_bucket_input_chunks_audio_when_chunk_size_set() -> None:
    body = b"a" * 10
    packet = DataPacket(
        validated_data={"content": body, "chunk_size": 4}
    )
    StorageInputParser().prepare_for_persist(
        packet, channel="bucket", operation="upload_direct", context=_ctx()
    )
    chunks = packet.validated_data["chunks"]
    assert chunks == [b"aaaa", b"aaaa", b"aa"]
    assert packet.parsed_data == {"chunks": chunks, "chunk_count": 3}


def test_bucket_output_recomposes_chunks_on_retrieve() -> None:
    packet = DataPacket(
        processed_data={
            "audio_id": "a1",
            "chunks": [b"hel", b"lo"],
        }
    )
    StorageOutputParser().after_read(
        packet, channel="bucket", operation="retrieve", context=_ctx()
    )
    assert packet.processed_data["content"] == b"hello"


def test_vector_input_drops_none_payload_attrs() -> None:
    packet = DataPacket(
        validated_data={
            "artefatti": [{"id": "a1", "vector": [0.1], "label": None}]
        }
    )
    StorageInputParser().prepare_for_persist(
        packet, channel="vector", operation="upsert", context=_ctx()
    )
    assert packet.validated_data["artefatti"] == [{"id": "a1", "vector": [0.1]}]


def test_vector_output_normalizes_search_results() -> None:
    packet = DataPacket(
        processed_data=[{"id": "p1", "score": 0.9, "payload": {"k": "v"}}]
    )
    StorageOutputParser().after_read(
        packet, channel="vector", operation="search", context=_ctx()
    )
    assert packet.processed_data == [
        {"id": "p1", "score": 0.9, "payload": {"k": "v"}}
    ]
