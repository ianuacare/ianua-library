"""Qdrant vector database adapter (optional dependency)."""

from __future__ import annotations

from typing import Any

try:  # Optional dependency
    from qdrant_client import QdrantClient as _QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:  # pragma: no cover - import-time optional dependency handling
    _QdrantClient = None  # type: ignore[assignment]
    qmodels = None  # type: ignore[assignment]


_DISTANCE_MAP: dict[str, str] = {
    "Cosine": "Cosine",
    "Dot": "Dot",
    "Euclid": "Euclid",
}


class QdrantDatabaseClient:
    """Persist and search points in Qdrant through the official SDK."""

    def __init__(
        self,
        *,
        url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is None and _QdrantClient is None:
            raise ImportError("QdrantDatabaseClient requires qdrant-client")
        if client is not None:
            self._client = client
        elif url is not None:
            self._client = _QdrantClient(url=url, api_key=api_key)
        elif host is not None:
            self._client = _QdrantClient(host=host, port=port or 6333, api_key=api_key)
        else:
            raise ValueError("QdrantDatabaseClient requires 'url' or 'host'")

    # -- VectorDatabaseClient API ---------------------------------------

    def ensure_collection(
        self,
        name: str,
        *,
        vector_size: int,
        distance: str = "Cosine",
    ) -> dict[str, Any]:
        if distance not in _DISTANCE_MAP:
            raise ValueError(f"Unsupported distance: {distance}")
        if qmodels is None:  # pragma: no cover - only when client injected without SDK
            raise ImportError("qdrant-client models are not available")

        existing = self._list_collection_names()
        if name in existing:
            return {"ok": True, "collection": name, "created": False}

        self._client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=int(vector_size),
                distance=qmodels.Distance[distance.upper()],
            ),
        )
        return {"ok": True, "collection": name, "created": True}

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> dict[str, Any]:
        if qmodels is None:  # pragma: no cover
            raise ImportError("qdrant-client models are not available")
        if not points:
            return {"ok": True, "collection": collection, "upserted": 0}
        first_vector = points[0].get("vector")
        if not isinstance(first_vector, list) or not first_vector:
            raise ValueError("each point must include a non-empty 'vector' list")
        self.ensure_collection(
            collection,
            vector_size=len(first_vector),
            distance="Cosine",
        )
        qpoints = [
            qmodels.PointStruct(
                id=point["id"],
                vector=[float(component) for component in point["vector"]],
                payload=dict(point.get("payload") or {}),
            )
            for point in points
        ]
        self._client.upsert(collection_name=collection, points=qpoints)
        return {"ok": True, "collection": collection, "upserted": len(qpoints)}

    def search(
        self,
        collection: str,
        *,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        query_filter = self._build_filter(filters)
        hits = self._client.search(
            collection_name=collection,
            query_vector=[float(component) for component in vector],
            query_filter=query_filter,
            limit=int(top_k),
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            {
                "id": getattr(hit, "id", None),
                "score": float(getattr(hit, "score", 0.0)),
                "payload": dict(getattr(hit, "payload", None) or {}),
            }
            for hit in hits
        ]

    def delete(
        self,
        collection: str,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if qmodels is None:  # pragma: no cover
            raise ImportError("qdrant-client models are not available")
        if ids is None and not filters:
            raise ValueError("delete requires 'ids' or 'filters'")
        if ids is not None:
            selector = qmodels.PointIdsList(points=list(ids))
        else:
            filter_obj = self._build_filter(filters)
            selector = qmodels.FilterSelector(filter=filter_obj)
        self._client.delete(collection_name=collection, points_selector=selector)
        return {"ok": True, "collection": collection}

    # -- Internal helpers -----------------------------------------------

    def _list_collection_names(self) -> set[str]:
        collections = self._client.get_collections()
        items = getattr(collections, "collections", None) or []
        return {getattr(item, "name", None) for item in items if getattr(item, "name", None)}

    @staticmethod
    def _build_filter(filters: dict[str, Any] | None) -> Any:
        if not filters:
            return None
        if qmodels is None:  # pragma: no cover
            raise ImportError("qdrant-client models are not available")
        must = [
            qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
            for key, value in filters.items()
        ]
        return qmodels.Filter(must=must)
