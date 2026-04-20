"""End-to-end: run_model(text_embedder) -> run_vector(upsert/search/delete)."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference import TextEmbedder
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.audit.service import AuditService
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.user import User
from ianuacare.core.orchestration.orchestrator import Orchestrator
from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser
from ianuacare.core.pipeline.data_manager import DataManager
from ianuacare.core.pipeline.pipeline import Pipeline
from ianuacare.core.pipeline.validator import DataValidator
from ianuacare.infrastructure.storage.bucket import InMemoryBucketClient
from ianuacare.infrastructure.storage.database import InMemoryDatabaseClient
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.vector import InMemoryVectorDatabaseClient
from ianuacare.infrastructure.storage.writer import Writer


# A tiny deterministic "encoder" used as the Callable provider backend:
# each word/sentence is mapped to a unit vector based on its first
# meaningful keyword, so that search with a matching prompt returns the
# expected artefact.
_KEYWORDS: dict[str, list[float]] = {
    "diabete": [1.0, 0.0, 0.0],
    "ipertensione": [0.0, 1.0, 0.0],
    "cefalea": [0.0, 0.0, 1.0],
}


def _encode_one(text: str) -> list[float]:
    normalized = text.strip().lower()
    for keyword, vector in _KEYWORDS.items():
        if keyword in normalized:
            return list(vector)
    return [0.1, 0.1, 0.1]


def _fake_provider(_: str, payload: Any) -> list[list[float]]:
    assert isinstance(payload, list)
    return [_encode_one(item) for item in payload]


def _build_pipeline() -> tuple[Pipeline, RequestContext, InMemoryVectorDatabaseClient]:
    db = InMemoryDatabaseClient()
    bucket = InMemoryBucketClient()
    vector_db = InMemoryVectorDatabaseClient()
    vector_db.ensure_collection("clinical_notes", vector_size=3)

    writer = Writer(db, bucket, vector_client=vector_db)
    reader = Reader(db, vector_client=vector_db)
    embedder = TextEmbedder(
        provider=CallableProvider(_fake_provider),
        model_name="e2e-embedder",
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
    user = User("user-e2e", "clinician", ["pipeline:run"])
    ctx = RequestContext(user, "ianuacare-demo", metadata={"model_key": "text_embedder"})
    return pipe, ctx, vector_db


def test_embed_upsert_search_delete_flow() -> None:
    pipe, ctx, vector_db = _build_pipeline()

    # Step 1: run the model to embed a clinical note, producing the
    # `artefatti` envelope expected by the vector flow.
    model_packet = pipe.run_model(
        {
            "id_artefatto_trascrizione": "tr-42",
            "text": "Paziente con diabete. Nessuna ipertensione riscontrata.",
            "split_sentences": True,
        },
        ctx,
    )
    assert "artefatti" in model_packet.processed_data
    artefatti = model_packet.processed_data["artefatti"]
    assert len(artefatti) == 1
    artefact = artefatti[0]
    assert artefact["id_artefatto_trascrizione"] == "tr-42"
    assert artefact["sentence"] == [
        "Paziente con diabete.",
        "Nessuna ipertensione riscontrata.",
    ]

    # Step 2: upsert the sentence-level vectors into the vector store.
    upsert_packet = pipe.run_vector(
        "upsert",
        {
            "collection": "clinical_notes",
            "vector_field": "sentence",
            "artefatti": artefatti,
        },
        ctx,
    )
    assert upsert_packet.processed_data["upserted"] == 2

    # Step 3: search by prompt; the text_embedder embeds "diabete" and
    # returns the matching sentence via filters.level='sentence'.
    search_packet = pipe.run_vector(
        "search",
        {
            "collection": "clinical_notes",
            "prompt": "diabete",
            "top_k": 1,
            "filters": {"level": "sentence"},
        },
        ctx,
    )
    hits = search_packet.processed_data
    assert len(hits) == 1
    assert hits[0]["payload"]["id_artefatto_trascrizione"] == "tr-42"
    assert hits[0]["payload"]["level"] == "sentence"
    assert "diabete" in hits[0]["payload"]["source_text"].lower()

    # Step 4: delete by filter removes all sentence-level points for the artefact.
    delete_packet = pipe.run_vector(
        "delete",
        {
            "collection": "clinical_notes",
            "filters": {"id_artefatto_trascrizione": "tr-42", "level": "sentence"},
        },
        ctx,
    )
    assert delete_packet.processed_data["deleted"] == 2
    assert vector_db.search("clinical_notes", vector=[1.0, 0.0, 0.0], top_k=5) == []


def test_prompt_search_with_extra_payload_filter() -> None:
    pipe, ctx, _ = _build_pipeline()

    # Upsert two artefacts at text level; they should be distinguishable by id.
    artefacts = [
        {
            "id_artefatto_trascrizione": "a",
            "text": "diabete scompensato",
            "text_vect": _encode_one("diabete"),
            "sentence": [],
            "sentence_vect": [],
            "words": [],
            "words_vect": [],
        },
        {
            "id_artefatto_trascrizione": "b",
            "text": "cefalea cronica",
            "text_vect": _encode_one("cefalea"),
            "sentence": [],
            "sentence_vect": [],
            "words": [],
            "words_vect": [],
        },
    ]
    pipe.run_vector(
        "upsert",
        {
            "collection": "clinical_notes",
            "vector_field": "text",
            "artefatti": artefacts,
        },
        ctx,
    )
    packet = pipe.run_vector(
        "search",
        {
            "collection": "clinical_notes",
            "prompt": "cefalea",
            "top_k": 5,
            "filters": {"level": "text", "id_artefatto_trascrizione": "b"},
        },
        ctx,
    )
    hits = packet.processed_data
    assert len(hits) == 1
    assert hits[0]["payload"]["id_artefatto_trascrizione"] == "b"
