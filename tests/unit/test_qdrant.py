"""Qdrant adapter (mocked SDK)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import ianuacare.infrastructure.storage.qdrant as qdrant_module
from ianuacare.infrastructure.storage.qdrant import QdrantDatabaseClient


def _make_qmodels_stub() -> MagicMock:
    """Return a ``qmodels`` stub whose attributes record the calls made on them."""
    stub = MagicMock()
    stub.Distance = MagicMock()
    stub.Distance.__getitem__.side_effect = lambda name: f"DISTANCE:{name}"
    stub.VectorParams.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
    stub.PointStruct.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
    stub.Filter.side_effect = lambda **kwargs: SimpleNamespace(kind="filter", **kwargs)
    stub.FieldCondition.side_effect = lambda **kwargs: SimpleNamespace(kind="field", **kwargs)
    stub.MatchValue.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
    stub.PointIdsList.side_effect = lambda **kwargs: SimpleNamespace(kind="ids", **kwargs)
    stub.FilterSelector.side_effect = lambda **kwargs: SimpleNamespace(
        kind="selector", **kwargs
    )
    return stub


class TestConstruction:
    def test_requires_url_or_host(self) -> None:
        with patch.object(qdrant_module, "_QdrantClient", MagicMock()):
            with pytest.raises(ValueError):
                QdrantDatabaseClient()

    def test_uses_injected_client(self) -> None:
        fake = MagicMock()
        db = QdrantDatabaseClient(client=fake)
        assert db._client is fake


class TestEnsureCollection:
    def test_creates_when_missing(self) -> None:
        fake = MagicMock()
        fake.get_collections.return_value = SimpleNamespace(collections=[])
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            out = db.ensure_collection("docs", vector_size=3)
        assert out == {"ok": True, "collection": "docs", "created": True}
        fake.create_collection.assert_called_once()

    def test_noop_when_exists(self) -> None:
        fake = MagicMock()
        fake.get_collections.return_value = SimpleNamespace(
            collections=[SimpleNamespace(name="docs")]
        )
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            out = db.ensure_collection("docs", vector_size=3)
        assert out == {"ok": True, "collection": "docs", "created": False}
        fake.create_collection.assert_not_called()

    def test_rejects_unsupported_distance(self) -> None:
        fake = MagicMock()
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            with pytest.raises(ValueError):
                db.ensure_collection("docs", vector_size=3, distance="Jaccard")


class TestUpsert:
    def test_auto_ensure_collection_before_upsert(self) -> None:
        fake = MagicMock()
        fake.get_collections.return_value = SimpleNamespace(collections=[])
        stub = _make_qmodels_stub()
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            out = db.upsert(
                "docs",
                [
                    {
                        "id": "p1",
                        "vector": [0.1, 0.2],
                        "payload": {"level": "text"},
                    }
                ],
            )
        assert out == {"ok": True, "collection": "docs", "upserted": 1}
        fake.create_collection.assert_called_once()
        fake.upsert.assert_called_once()

    def test_empty_upsert_is_noop(self) -> None:
        fake = MagicMock()
        stub = _make_qmodels_stub()
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            out = db.upsert("docs", [])
        assert out == {"ok": True, "collection": "docs", "upserted": 0}
        fake.upsert.assert_not_called()

    def test_builds_point_structs(self) -> None:
        fake = MagicMock()
        stub = _make_qmodels_stub()
        fake.get_collections.return_value = SimpleNamespace(
            collections=[SimpleNamespace(name="docs")]
        )
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            out = db.upsert(
                "docs",
                [
                    {
                        "id": "p1",
                        "vector": [0.1, 0.2],
                        "payload": {"level": "text"},
                    }
                ],
            )
        assert out == {"ok": True, "collection": "docs", "upserted": 1}
        stub.PointStruct.assert_called_once_with(
            id="p1",
            vector=[0.1, 0.2],
            payload={"level": "text"},
        )
        fake.upsert.assert_called_once()


class TestSearch:
    def test_passes_filter_and_limit(self) -> None:
        fake = MagicMock()
        fake.search.return_value = [
            SimpleNamespace(id="p1", score=0.9, payload={"level": "sentence"}),
        ]
        stub = _make_qmodels_stub()
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            hits = db.search(
                "docs",
                vector=[1.0, 0.0],
                top_k=5,
                filters={"level": "sentence"},
                score_threshold=0.1,
            )
        assert hits == [{"id": "p1", "score": 0.9, "payload": {"level": "sentence"}}]
        assert fake.search.call_args.kwargs["limit"] == 5
        assert fake.search.call_args.kwargs["score_threshold"] == 0.1
        stub.FieldCondition.assert_called_once()

    def test_no_filter_sends_none(self) -> None:
        fake = MagicMock()
        fake.search.return_value = []
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            db.search("docs", vector=[0.0, 1.0], top_k=3)
        assert fake.search.call_args.kwargs["query_filter"] is None


class TestDelete:
    def test_delete_by_ids_uses_ids_selector(self) -> None:
        fake = MagicMock()
        stub = _make_qmodels_stub()
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            out = db.delete("docs", ids=["a", "b"])
        assert out == {"ok": True, "collection": "docs"}
        stub.PointIdsList.assert_called_once_with(points=["a", "b"])
        fake.delete.assert_called_once()

    def test_delete_by_filters_uses_filter_selector(self) -> None:
        fake = MagicMock()
        stub = _make_qmodels_stub()
        with patch.object(qdrant_module, "qmodels", stub):
            db = QdrantDatabaseClient(client=fake)
            db.delete("docs", filters={"level": "words"})
        stub.FilterSelector.assert_called_once()
        stub.FieldCondition.assert_called_once()

    def test_requires_ids_or_filters(self) -> None:
        fake = MagicMock()
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            with pytest.raises(ValueError):
                db.delete("docs")


class TestScroll:
    def test_paginates_until_exhausted(self) -> None:
        r1 = SimpleNamespace(id="a", payload={"k": 1}, vector=None)
        r2 = SimpleNamespace(id="b", payload={"k": 2}, vector=None)
        fake = MagicMock()
        fake.scroll.side_effect = [
            ([r1], "off-1"),
            ([r2], None),
        ]
        with patch.object(qdrant_module, "qmodels", _make_qmodels_stub()):
            db = QdrantDatabaseClient(client=fake)
            rows = db.scroll("docs", filters={"level": "text"}, batch_size=1)
        assert rows == [
            {"id": "a", "payload": {"k": 1}},
            {"id": "b", "payload": {"k": 2}},
        ]
        assert fake.scroll.call_count == 2
        assert fake.scroll.call_args_list[0].kwargs["limit"] == 1
        assert fake.scroll.call_args_list[1].kwargs["offset"] == "off-1"
