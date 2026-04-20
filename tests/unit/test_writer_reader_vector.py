"""Writer and Reader vector methods."""

from __future__ import annotations

import pytest

from ianuacare.core.exceptions.errors import StorageError, ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.user import User
from ianuacare.infrastructure.storage.bucket import InMemoryBucketClient
from ianuacare.infrastructure.storage.database import InMemoryDatabaseClient
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.vector import InMemoryVectorDatabaseClient
from ianuacare.infrastructure.storage.writer import Writer


@pytest.fixture
def ctx() -> RequestContext:
    user = User(user_id="u-1", role="clinician", permissions=["pipeline:run"])
    return RequestContext(user=user, product="test")


@pytest.fixture
def vector_db() -> InMemoryVectorDatabaseClient:
    client = InMemoryVectorDatabaseClient()
    client.ensure_collection("docs", vector_size=2)
    return client


@pytest.fixture
def writer(vector_db: InMemoryVectorDatabaseClient) -> Writer:
    return Writer(
        db_client=InMemoryDatabaseClient(),
        bucket_client=InMemoryBucketClient(),
        vector_client=vector_db,
    )


@pytest.fixture
def reader(vector_db: InMemoryVectorDatabaseClient) -> Reader:
    return Reader(
        db_client=InMemoryDatabaseClient(),
        vector_client=vector_db,
    )


def _artefact(artefact_id: str = "tr-1") -> dict[str, object]:
    return {
        "id_artefatto_trascrizione": artefact_id,
        "text": "ciao mondo",
        "text_vect": [1.0, 0.0],
        "sentence": ["ciao.", "mondo!"],
        "sentence_vect": [[1.0, 0.0], [0.0, 1.0]],
        "words": ["ciao", "mondo"],
        "words_vect": [[0.9, 0.1], [0.1, 0.9]],
    }


class TestWriteVectorUpsert:
    def test_text_level_produces_one_point(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        result = writer.write_vector_upsert(
            "docs",
            [_artefact()],
            vector_field="text",
            context=ctx,
        )
        assert result == {"ok": True, "collection": "docs", "upserted": 1}
        hits = vector_db.search("docs", vector=[1.0, 0.0], top_k=5)
        assert [hit["id"] for hit in hits] == ["tr-1:text:0"]
        assert hits[0]["payload"] == {
            "user_id": "u-1",
            "product": "test",
            "id_artefatto_trascrizione": "tr-1",
            "level": "text",
            "index": 0,
            "source_text": "ciao mondo",
        }

    def test_sentence_level_produces_one_point_per_sentence(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert(
            "docs",
            [_artefact()],
            vector_field="sentence",
            context=ctx,
        )
        hits = vector_db.search("docs", vector=[1.0, 0.0], top_k=5)
        ids = [hit["id"] for hit in hits]
        assert set(ids) == {"tr-1:sentence:0", "tr-1:sentence:1"}

    def test_words_level_produces_one_point_per_word(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert(
            "docs",
            [_artefact()],
            vector_field="words",
            context=ctx,
        )
        hits = vector_db.search("docs", vector=[0.9, 0.1], top_k=5)
        assert {hit["id"] for hit in hits} == {"tr-1:words:0", "tr-1:words:1"}

    def test_multiple_artefacts(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert(
            "docs",
            [_artefact("a"), _artefact("b")],
            vector_field="text",
            context=ctx,
        )
        hits = vector_db.search("docs", vector=[1.0, 0.0], top_k=5)
        assert {hit["id"] for hit in hits} == {"a:text:0", "b:text:0"}

    def test_rejects_invalid_vector_field(
        self, writer: Writer, ctx: RequestContext
    ) -> None:
        with pytest.raises(ValidationError):
            writer.write_vector_upsert(
                "docs",
                [_artefact()],
                vector_field="bogus",
                context=ctx,
            )

    def test_rejects_missing_artefact_id(
        self, writer: Writer, ctx: RequestContext
    ) -> None:
        bad = _artefact()
        del bad["id_artefatto_trascrizione"]
        with pytest.raises(ValidationError):
            writer.write_vector_upsert(
                "docs",
                [bad],
                vector_field="text",
                context=ctx,
            )

    def test_rejects_mismatched_lengths(
        self, writer: Writer, ctx: RequestContext
    ) -> None:
        bad = _artefact()
        bad["sentence"] = ["only one"]
        with pytest.raises(ValidationError):
            writer.write_vector_upsert(
                "docs",
                [bad],
                vector_field="sentence",
                context=ctx,
            )

    def test_requires_vector_client(
        self, ctx: RequestContext
    ) -> None:
        writer = Writer(
            db_client=InMemoryDatabaseClient(),
            bucket_client=InMemoryBucketClient(),
        )
        with pytest.raises(StorageError):
            writer.write_vector_upsert(
                "docs",
                [_artefact()],
                vector_field="text",
                context=ctx,
            )

    def test_upsert_overwrites_with_same_id(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert("docs", [_artefact()], vector_field="text", context=ctx)
        artefact = _artefact()
        artefact["text"] = "nuovo testo"
        artefact["text_vect"] = [0.0, 1.0]
        writer.write_vector_upsert("docs", [artefact], vector_field="text", context=ctx)
        hits = vector_db.search("docs", vector=[0.0, 1.0], top_k=5)
        assert len(hits) == 1
        assert hits[0]["payload"]["source_text"] == "nuovo testo"


class TestWriteVectorDelete:
    def test_delete_by_ids(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert(
            "docs", [_artefact()], vector_field="sentence", context=ctx
        )
        result = writer.write_vector_delete(
            "docs", ids=["tr-1:sentence:0"], context=ctx
        )
        assert result["deleted"] == 1

    def test_delete_by_filters(
        self, writer: Writer, vector_db: InMemoryVectorDatabaseClient, ctx: RequestContext
    ) -> None:
        writer.write_vector_upsert(
            "docs", [_artefact()], vector_field="sentence", context=ctx
        )
        result = writer.write_vector_delete(
            "docs",
            filters={"id_artefatto_trascrizione": "tr-1"},
            context=ctx,
        )
        assert result["deleted"] == 2

    def test_rejects_no_criteria(
        self, writer: Writer, ctx: RequestContext
    ) -> None:
        with pytest.raises(ValidationError):
            writer.write_vector_delete("docs", context=ctx)


class TestReadVectorSearch:
    def test_filters_by_level(
        self,
        writer: Writer,
        reader: Reader,
        ctx: RequestContext,
    ) -> None:
        writer.write_vector_upsert("docs", [_artefact()], vector_field="text", context=ctx)
        writer.write_vector_upsert(
            "docs", [_artefact()], vector_field="sentence", context=ctx
        )
        hits = reader.read_vector_search(
            "docs",
            vector=[1.0, 0.0],
            top_k=5,
            filters={"level": "sentence"},
            context=ctx,
        )
        assert all(hit["payload"]["level"] == "sentence" for hit in hits)

    def test_level_required(
        self, reader: Reader, ctx: RequestContext
    ) -> None:
        with pytest.raises(ValidationError):
            reader.read_vector_search(
                "docs",
                vector=[1.0, 0.0],
                filters={},
                context=ctx,
            )

    def test_level_must_be_valid(
        self, reader: Reader, ctx: RequestContext
    ) -> None:
        with pytest.raises(ValidationError):
            reader.read_vector_search(
                "docs",
                vector=[1.0, 0.0],
                filters={"level": "paragraph"},
                context=ctx,
            )

    def test_rejects_empty_vector(
        self, reader: Reader, ctx: RequestContext
    ) -> None:
        with pytest.raises(ValidationError):
            reader.read_vector_search(
                "docs",
                vector=[],
                filters={"level": "text"},
                context=ctx,
            )

    def test_requires_vector_client(self, ctx: RequestContext) -> None:
        reader = Reader(db_client=InMemoryDatabaseClient())
        with pytest.raises(StorageError):
            reader.read_vector_search(
                "docs",
                vector=[1.0, 0.0],
                filters={"level": "text"},
                context=ctx,
            )

    def test_forwards_extra_filters(
        self,
        writer: Writer,
        reader: Reader,
        ctx: RequestContext,
    ) -> None:
        writer.write_vector_upsert(
            "docs", [_artefact("a"), _artefact("b")], vector_field="text", context=ctx
        )
        hits = reader.read_vector_search(
            "docs",
            vector=[1.0, 0.0],
            top_k=5,
            filters={"level": "text", "id_artefatto_trascrizione": "a"},
            context=ctx,
        )
        assert [hit["payload"]["id_artefatto_trascrizione"] for hit in hits] == ["a"]
