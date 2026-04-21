"""Pipeline.run_vector flow over an InMemory vector backend."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference import TextEmbedder
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.audit.service import AuditService
from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.vector import InMemoryVectorDatabaseClient
from ianuacare.infrastructure.storage.writer import Writer


def _lookup_encoder(_: str, payload: Any) -> list[list[float]]:
    """Deterministic 2-dim encoder: ``diabete`` -> [1,0], ``ipertensione`` -> [0,1]."""
    assert isinstance(payload, list)
    table = {
        "diabete": [1.0, 0.0],
        "ipertensione": [0.0, 1.0],
    }
    return [list(table.get(item.strip().lower(), [0.5, 0.5])) for item in payload]


@pytest.fixture
def pipeline_fixture(db, bucket, context):
    vector_db = InMemoryVectorDatabaseClient()
    vector_db.ensure_collection("clinical", vector_size=2)
    writer = Writer(db, bucket, vector_client=vector_db)
    reader = Reader(db, vector_client=vector_db)
    embedder = TextEmbedder(
        provider=CallableProvider(_lookup_encoder),
        model_name="test-embedder",
    )
    orch = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"text_embedder": embedder},
        default_model_key="text_embedder",
    )
    pipe = Pipeline(
        DataManager(),
        DataValidator(),
        writer,
        reader,
        orch,
        AuditService(db),
    )
    return pipe, vector_db, context


def _artefact(artefact_id: str, text: str, vec: list[float]) -> dict[str, object]:
    return {
        "id_artefatto_trascrizione": artefact_id,
        "text": text,
        "text_vect": vec,
        "sentence": [],
        "sentence_vect": [],
        "words": [],
        "words_vect": [],
    }


class TestUpsert:
    def test_writes_points_to_collection(self, pipeline_fixture) -> None:
        pipe, vector_db, ctx = pipeline_fixture
        packet = pipe.run_vector(
            "upsert",
            {
                "collection": "clinical",
                "vector_field": "text",
                "artefatti": [
                    _artefact("a", "diabete", [1.0, 0.0]),
                    _artefact("b", "ipertensione", [0.0, 1.0]),
                ],
            },
            ctx,
        )
        assert packet.processed_data["upserted"] == 2
        hits = vector_db.search("clinical", vector=[1.0, 0.0], top_k=5)
        assert {hit["id"] for hit in hits} == {"a:text:0", "b:text:0"}

    def test_invalid_vector_field_rejected(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector(
                "upsert",
                {
                    "collection": "clinical",
                    "vector_field": "bogus",
                    "artefatti": [_artefact("a", "x", [1.0, 0.0])],
                },
                ctx,
            )

    def test_empty_artefatti_rejected(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector(
                "upsert",
                {
                    "collection": "clinical",
                    "vector_field": "text",
                    "artefatti": [],
                },
                ctx,
            )


class TestSearch:
    def test_with_vector(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        pipe.run_vector(
            "upsert",
            {
                "collection": "clinical",
                "vector_field": "text",
                "artefatti": [
                    _artefact("a", "diabete", [1.0, 0.0]),
                    _artefact("b", "ipertensione", [0.0, 1.0]),
                ],
            },
            ctx,
        )
        packet = pipe.run_vector(
            "search",
            {
                "collection": "clinical",
                "vector": [1.0, 0.0],
                "top_k": 1,
                "filters": {"level": "text"},
            },
            ctx,
        )
        assert len(packet.processed_data) == 1
        assert packet.processed_data[0]["payload"]["id_artefatto_trascrizione"] == "a"

    def test_with_prompt_embeds_via_text_embedder(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        pipe.run_vector(
            "upsert",
            {
                "collection": "clinical",
                "vector_field": "text",
                "artefatti": [
                    _artefact("a", "diabete", [1.0, 0.0]),
                    _artefact("b", "ipertensione", [0.0, 1.0]),
                ],
            },
            ctx,
        )
        packet = pipe.run_vector(
            "search",
            {
                "collection": "clinical",
                "prompt": "diabete",
                "top_k": 1,
                "filters": {"level": "text"},
            },
            ctx,
        )
        assert packet.processed_data[0]["payload"]["id_artefatto_trascrizione"] == "a"

    def test_missing_level_rejected(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector(
                "search",
                {
                    "collection": "clinical",
                    "vector": [1.0, 0.0],
                    "filters": {},
                },
                ctx,
            )

    def test_missing_both_vector_and_prompt(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector(
                "search",
                {
                    "collection": "clinical",
                    "filters": {"level": "text"},
                },
                ctx,
            )


class TestDelete:
    def test_by_ids(self, pipeline_fixture) -> None:
        pipe, vector_db, ctx = pipeline_fixture
        pipe.run_vector(
            "upsert",
            {
                "collection": "clinical",
                "vector_field": "text",
                "artefatti": [_artefact("a", "diabete", [1.0, 0.0])],
            },
            ctx,
        )
        packet = pipe.run_vector(
            "delete",
            {"collection": "clinical", "ids": ["a:text:0"]},
            ctx,
        )
        assert packet.processed_data["deleted"] == 1
        assert vector_db.search("clinical", vector=[1.0, 0.0], top_k=5) == []

    def test_requires_ids_or_filters(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector("delete", {"collection": "clinical"}, ctx)


class TestScroll:
    def test_returns_all_points(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        pipe.run_vector(
            "upsert",
            {
                "collection": "clinical",
                "vector_field": "text",
                "artefatti": [
                    _artefact("a", "diabete", [1.0, 0.0]),
                    _artefact("b", "ipertensione", [0.0, 1.0]),
                ],
            },
            ctx,
        )
        packet = pipe.run_vector(
            "scroll",
            {"collection": "clinical"},
            ctx,
        )
        ids = {row["id"] for row in packet.processed_data}
        assert ids == {"a:text:0", "b:text:0"}
        levels = {row["payload"]["level"] for row in packet.processed_data}
        assert levels == {"text"}


class TestOperation:
    def test_unknown_operation_rejected(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector("bogus", {"collection": "clinical"}, ctx)

    def test_missing_collection_rejected(self, pipeline_fixture) -> None:
        pipe, _, ctx = pipeline_fixture
        with pytest.raises(ValidationError):
            pipe.run_vector(
                "delete",
                {"ids": ["x"]},
                ctx,
            )
