"""Vector database abstraction (protocol + in-memory implementation)."""

from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorDatabaseClient(Protocol):
    """Contract for vector-search-capable backends (Qdrant and compatible)."""

    def ensure_collection(
        self,
        name: str,
        *,
        vector_size: int,
        distance: str = "Cosine",
    ) -> dict[str, Any]:
        """Create ``name`` if it does not already exist."""
        ...

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> dict[str, Any]:
        """Insert or update ``points`` (each ``{id, vector, payload}``) in ``collection``."""
        ...

    def search(
        self,
        collection: str,
        *,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return the ``top_k`` nearest points to ``vector`` optionally filtered by payload."""
        ...

    def delete(
        self,
        collection: str,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Delete points matching ``ids`` or ``filters`` (exact-match payload)."""
        ...

    def scroll(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None = None,
        batch_size: int = 256,
        with_vectors: bool = False,
        with_payload: bool = True,
    ) -> list[dict[str, Any]]:
        """Iterate all points in ``collection`` (optionally filtered), like Qdrant ``scroll``."""
        ...


class InMemoryVectorDatabaseClient:
    """In-memory ``VectorDatabaseClient`` for development and tests.

    Points are stored per collection as a list of ``{id, vector, payload}``
    dictionaries. ``search`` uses the distance declared at
    ``ensure_collection`` time (``Cosine`` by default); ``Dot`` and
    ``Euclid`` are also supported. Filters are applied as exact-match
    against the point ``payload`` mapping.
    """

    def __init__(
        self,
        collections: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._collections: dict[str, list[dict[str, Any]]] = (
            {name: list(points) for name, points in collections.items()}
            if collections
            else {}
        )
        self._meta: dict[str, dict[str, Any]] = {}

    def ensure_collection(
        self,
        name: str,
        *,
        vector_size: int,
        distance: str = "Cosine",
    ) -> dict[str, Any]:
        if distance not in {"Cosine", "Dot", "Euclid"}:
            raise ValueError(f"Unsupported distance: {distance}")
        if name not in self._collections:
            self._collections[name] = []
        self._meta.setdefault(
            name,
            {"vector_size": int(vector_size), "distance": distance},
        )
        return {"ok": True, "collection": name, **self._meta[name]}

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(points, list):
            raise TypeError("points must be a list")
        if not points:
            return {"ok": True, "collection": collection, "upserted": 0}
        first_vector = points[0].get("vector")
        if not isinstance(first_vector, list) or not first_vector:
            raise ValueError("each point must include a non-empty 'vector' list")
        if collection not in self._collections:
            self.ensure_collection(
                collection,
                vector_size=len(first_vector),
                distance="Cosine",
            )
        bucket = self._collections.setdefault(collection, [])
        by_id = {point["id"]: index for index, point in enumerate(bucket)}
        upserted = 0
        for point in points:
            if "id" not in point or "vector" not in point:
                raise ValueError("each point must include 'id' and 'vector'")
            normalized = {
                "id": point["id"],
                "vector": [float(component) for component in point["vector"]],
                "payload": dict(point.get("payload") or {}),
            }
            if len(normalized["vector"]) != self._meta[collection]["vector_size"]:
                raise ValueError(
                    "point vector size does not match collection vector_size"
                )
            if point["id"] in by_id:
                bucket[by_id[point["id"]]] = normalized
            else:
                by_id[point["id"]] = len(bucket)
                bucket.append(normalized)
            upserted += 1
        return {"ok": True, "collection": collection, "upserted": upserted}

    def search(
        self,
        collection: str,
        *,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        bucket = self._collections.get(collection, [])
        distance = self._meta.get(collection, {}).get("distance", "Cosine")
        query = [float(component) for component in vector]
        scored: list[tuple[float, dict[str, Any]]] = []
        for point in bucket:
            if filters and not self._matches(point.get("payload", {}), filters):
                continue
            score = self._score(query, point["vector"], distance)
            if score_threshold is not None and score < score_threshold:
                continue
            scored.append((score, point))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        hits = scored[: max(top_k, 0)]
        return [
            {
                "id": point["id"],
                "score": score,
                "payload": dict(point.get("payload", {})),
            }
            for score, point in hits
        ]

    def delete(
        self,
        collection: str,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if ids is None and not filters:
            raise ValueError("delete requires 'ids' or 'filters'")
        bucket = self._collections.get(collection, [])
        id_set = set(ids) if ids else None
        kept: list[dict[str, Any]] = []
        for point in bucket:
            if id_set is not None and point["id"] in id_set:
                continue
            if filters and self._matches(point.get("payload", {}), filters):
                continue
            kept.append(point)
        deleted = len(bucket) - len(kept)
        self._collections[collection] = kept
        return {"ok": True, "collection": collection, "deleted": deleted}

    def scroll(
        self,
        collection: str,
        *,
        filters: dict[str, Any] | None = None,
        batch_size: int = 256,
        with_vectors: bool = False,
        with_payload: bool = True,
    ) -> list[dict[str, Any]]:
        """Return all points (``batch_size`` only affects API parity with Qdrant)."""
        _ = batch_size
        bucket = self._collections.get(collection, [])
        rows: list[dict[str, Any]] = []
        for point in bucket:
            payload = point.get("payload") or {}
            if filters and not self._matches(dict(payload), filters):
                continue
            row: dict[str, Any] = {"id": point["id"]}
            if with_payload:
                row["payload"] = dict(payload)
            if with_vectors:
                row["vector"] = list(point["vector"])
            rows.append(row)
        return rows

    @staticmethod
    def _matches(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(payload.get(key) == value for key, value in filters.items())

    @staticmethod
    def _score(query: list[float], stored: list[float], distance: str) -> float:
        """Return a similarity score (higher is better) according to ``distance``."""
        if len(query) != len(stored):
            return float("-inf")
        if distance == "Dot":
            return sum(a * b for a, b in zip(query, stored, strict=True))
        if distance == "Euclid":
            sq = sum((a - b) ** 2 for a, b in zip(query, stored, strict=True))
            return -math.sqrt(sq)
        # Cosine (default): normalize vectors and compute inner product.
        norm_q = math.sqrt(sum(component * component for component in query))
        norm_s = math.sqrt(sum(component * component for component in stored))
        if norm_q == 0.0 or norm_s == 0.0:
            return 0.0
        dot = sum(a * b for a, b in zip(query, stored, strict=True))
        return dot / (norm_q * norm_s)
