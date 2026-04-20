"""InMemoryVectorDatabaseClient."""

from __future__ import annotations

import math

import pytest

from ianuacare.infrastructure.storage.vector import (
    InMemoryVectorDatabaseClient,
    VectorDatabaseClient,
)


def _client() -> InMemoryVectorDatabaseClient:
    return InMemoryVectorDatabaseClient()


class TestProtocol:
    def test_inmemory_satisfies_protocol(self) -> None:
        assert isinstance(_client(), VectorDatabaseClient)


class TestEnsureCollection:
    def test_creates_collection_with_defaults(self) -> None:
        c = _client()
        result = c.ensure_collection("docs", vector_size=3)
        assert result["ok"] is True
        assert result["collection"] == "docs"
        assert result["vector_size"] == 3
        assert result["distance"] == "Cosine"

    def test_idempotent(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=3)
        c.upsert("docs", [{"id": "a", "vector": [1.0, 0.0, 0.0]}])
        c.ensure_collection("docs", vector_size=3)
        assert len(c.search("docs", vector=[1.0, 0.0, 0.0], top_k=5)) == 1

    def test_rejects_unsupported_distance(self) -> None:
        c = _client()
        with pytest.raises(ValueError):
            c.ensure_collection("docs", vector_size=3, distance="Jaccard")


class TestUpsert:
    def test_auto_creates_collection_if_missing(self) -> None:
        c = _client()
        result = c.upsert(
            "docs",
            [{"id": "a", "vector": [1.0, 0.0], "payload": {"level": "text"}}],
        )
        assert result == {"ok": True, "collection": "docs", "upserted": 1}
        assert c.search("docs", vector=[1.0, 0.0], top_k=5)[0]["id"] == "a"

    def test_rejects_vector_size_mismatch_with_existing_collection(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        with pytest.raises(ValueError):
            c.upsert("docs", [{"id": "a", "vector": [1.0, 0.0, 0.0]}])

    def test_empty_upsert_is_noop(self) -> None:
        c = _client()
        assert c.upsert("docs", []) == {"ok": True, "collection": "docs", "upserted": 0}

    def test_inserts_new_points(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        result = c.upsert(
            "docs",
            [
                {"id": "a", "vector": [1.0, 0.0], "payload": {"level": "text"}},
                {"id": "b", "vector": [0.0, 1.0], "payload": {"level": "text"}},
            ],
        )
        assert result == {"ok": True, "collection": "docs", "upserted": 2}

    def test_updates_existing_point(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert("docs", [{"id": "a", "vector": [1.0, 0.0], "payload": {"v": 1}}])
        c.upsert("docs", [{"id": "a", "vector": [0.0, 1.0], "payload": {"v": 2}}])
        hits = c.search("docs", vector=[0.0, 1.0], top_k=5)
        assert len(hits) == 1
        assert hits[0]["id"] == "a"
        assert hits[0]["payload"] == {"v": 2}

    def test_rejects_missing_fields(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        with pytest.raises(ValueError):
            c.upsert("docs", [{"id": "a"}])


class TestSearch:
    def test_cosine_ranking(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [
                {"id": "x", "vector": [1.0, 0.0], "payload": {"level": "text"}},
                {"id": "y", "vector": [0.0, 1.0], "payload": {"level": "text"}},
                {"id": "z", "vector": [0.7, 0.7], "payload": {"level": "text"}},
            ],
        )
        hits = c.search("docs", vector=[1.0, 0.0], top_k=3)
        assert [hit["id"] for hit in hits] == ["x", "z", "y"]
        assert hits[0]["score"] == pytest.approx(1.0)

    def test_filter_by_payload(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [
                {"id": "x", "vector": [1.0, 0.0], "payload": {"level": "text"}},
                {"id": "y", "vector": [1.0, 0.0], "payload": {"level": "sentence"}},
            ],
        )
        hits = c.search(
            "docs",
            vector=[1.0, 0.0],
            top_k=5,
            filters={"level": "sentence"},
        )
        assert [hit["id"] for hit in hits] == ["y"]

    def test_score_threshold(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [
                {"id": "x", "vector": [1.0, 0.0]},
                {"id": "y", "vector": [0.0, 1.0]},
            ],
        )
        hits = c.search("docs", vector=[1.0, 0.0], top_k=5, score_threshold=0.5)
        assert [hit["id"] for hit in hits] == ["x"]

    def test_top_k_limits(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [{"id": str(i), "vector": [1.0, float(i)]} for i in range(5)],
        )
        hits = c.search("docs", vector=[1.0, 0.0], top_k=2)
        assert len(hits) == 2

    def test_returns_empty_for_missing_collection(self) -> None:
        c = _client()
        assert c.search("missing", vector=[1.0, 0.0]) == []

    def test_dot_distance(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2, distance="Dot")
        c.upsert(
            "docs",
            [
                {"id": "x", "vector": [1.0, 0.0]},
                {"id": "y", "vector": [2.0, 0.0]},
            ],
        )
        hits = c.search("docs", vector=[1.0, 0.0], top_k=2)
        assert [hit["id"] for hit in hits] == ["y", "x"]

    def test_euclid_distance(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2, distance="Euclid")
        c.upsert(
            "docs",
            [
                {"id": "near", "vector": [1.0, 0.0]},
                {"id": "far", "vector": [10.0, 0.0]},
            ],
        )
        hits = c.search("docs", vector=[1.0, 0.0], top_k=2)
        assert hits[0]["id"] == "near"
        assert math.isclose(hits[0]["score"], 0.0, abs_tol=1e-9)


class TestDelete:
    def test_delete_by_ids(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [
                {"id": "a", "vector": [1.0, 0.0]},
                {"id": "b", "vector": [0.0, 1.0]},
            ],
        )
        result = c.delete("docs", ids=["a"])
        assert result == {"ok": True, "collection": "docs", "deleted": 1}
        remaining = c.search("docs", vector=[1.0, 0.0], top_k=5)
        assert [hit["id"] for hit in remaining] == ["b"]

    def test_delete_by_filters(self) -> None:
        c = _client()
        c.ensure_collection("docs", vector_size=2)
        c.upsert(
            "docs",
            [
                {"id": "a", "vector": [1.0, 0.0], "payload": {"level": "text"}},
                {"id": "b", "vector": [1.0, 0.0], "payload": {"level": "sentence"}},
            ],
        )
        result = c.delete("docs", filters={"level": "sentence"})
        assert result["deleted"] == 1

    def test_delete_requires_ids_or_filters(self) -> None:
        c = _client()
        with pytest.raises(ValueError):
            c.delete("docs")
