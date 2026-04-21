"""Generic label clustering model based on embedding vectors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.text_embedder import TextEmbedder
from ianuacare.core.exceptions.errors import InferenceError, ValidationError


class LabelClusterer(BaseAIModel):
    """Cluster vectors and map discovered clusters to caller-provided labels.

    Optional payload keys ``texts`` and ``point_ids`` align with ``vectors`` and are
    echoed in the result (defaults: empty strings and ``None`` ids).
    """

    def __init__(
        self,
        text_embedder: TextEmbedder | None = None,
        random_state: int = 42,
    ) -> None:
        self._text_embedder = text_embedder or TextEmbedder()
        self._random_state = random_state

    def run(self, payload: Any) -> dict[str, Any]:
        vectors = self._extract_vectors(payload)
        texts, point_ids = self._extract_point_metadata(payload, len(vectors))
        label_clusters = self._extract_label_clusters(payload)
        n_clusters = min(len(vectors), len(label_clusters))
        if n_clusters == 0:
            return {
                "labels": [],
                "assigned_labels": [],
                "cluster_to_label": {},
                "projected_vectors": [],
                "explained_variance_ratio": [],
                "texts": texts, #TO DO: forse non c'è coglione
                "point_ids": point_ids,
            }

        labels, centroids = self._cluster_in_original_space(vectors, n_clusters)
        prototypes = self._build_label_prototypes(label_clusters)
        cluster_to_label = self._map_clusters_to_labels(centroids, prototypes)
        assigned_labels = [cluster_to_label[label] for label in labels]
        projected_vectors, explained_variance_ratio = self._project_for_visualization(vectors)
        return {
            "labels": labels,
            "assigned_labels": assigned_labels,
            "cluster_to_label": cluster_to_label,
            "projected_vectors": projected_vectors,
            "explained_variance_ratio": explained_variance_ratio,
            "texts": texts,
            "point_ids": point_ids,
        }

    def _extract_vectors(self, payload: Any) -> list[list[float]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("label_clusterer payload must be a mapping")
        raw_vectors = payload.get("vectors")
        if not isinstance(raw_vectors, list) or not raw_vectors:
            raise ValidationError("vectors must be a non-empty list")

        vectors: list[list[float]] = []
        for row_index, vector in enumerate(raw_vectors):
            if not isinstance(vector, list) or not vector:
                raise ValidationError(f"vector at index {row_index} must be a non-empty list")
            try:
                coerced = [float(component) for component in vector]
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"vector at index {row_index} contains non-numeric components"
                ) from exc
            vectors.append(coerced)
        dim = len(vectors[0])
        if any(len(vector) != dim for vector in vectors):
            raise ValidationError("all vectors must have the same dimensionality")
        return vectors

    def _extract_point_metadata(
        self, payload: Mapping[Any, Any], vector_count: int
    ) -> tuple[list[str], list[Any]]:
        """Optional per-vector text and point id, aligned with ``vectors`` order."""
        raw_texts = payload.get("texts", [])
        if not isinstance(raw_texts, list):
            raise ValidationError("texts must be a list when provided")
        texts: list[str] = []
        for index, value in enumerate(raw_texts):
            if not isinstance(value, str):
                raise ValidationError(f"text at index {index} must be a string")
            texts.append(value)
        if texts and len(texts) != vector_count:
            raise ValidationError("texts length must match vectors length")
        if not texts:
            texts = [""] * vector_count

        raw_ids = payload.get("point_ids")
        if raw_ids is None:
            point_ids = [None] * vector_count
        else:
            if not isinstance(raw_ids, list):
                raise ValidationError("point_ids must be a list when provided")
            if len(raw_ids) != vector_count:
                raise ValidationError("point_ids length must match vectors length")
            point_ids = list(raw_ids)

        return texts, point_ids

    def _extract_label_clusters(self, payload: Any) -> dict[str, list[str]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("label_clusterer payload must be a mapping")
        raw = payload.get("label_clusters")
        if not isinstance(raw, Mapping) or not raw:
            raise ValidationError("label_clusters must be a non-empty mapping")
        parsed: dict[str, list[str]] = {}
        for key, anchors in raw.items():
            if not isinstance(key, str) or not key:
                raise ValidationError("label_clusters keys must be non-empty strings")
            if not isinstance(anchors, list) or not anchors:
                raise ValidationError(f"label_clusters['{key}'] must be a non-empty list")
            parsed_anchors: list[str] = []
            for idx, anchor in enumerate(anchors):
                if not isinstance(anchor, str) or not anchor.strip():
                    raise ValidationError(
                        f"label_clusters['{key}'][{idx}] must be a non-empty string"
                    )
                parsed_anchors.append(anchor)
            parsed[key] = parsed_anchors
        return parsed

    def _cluster_in_original_space(
        self, vectors: list[list[float]], n_clusters: int
    ) -> tuple[list[int], list[list[float]]]:
        try:
            kmeans_mod = import_module("sklearn.cluster")
            kmeans_cls = getattr(kmeans_mod, "KMeans")
        except ImportError as exc:
            raise InferenceError("scikit-learn is required for LabelClusterer clustering") from exc

        model = kmeans_cls(n_clusters=n_clusters, random_state=self._random_state, n_init="auto")
        labels_nd = model.fit_predict(vectors)
        labels = [int(label) for label in labels_nd.tolist()]
        centroids = [
            [float(component) for component in row]
            for row in model.cluster_centers_.tolist()
        ]
        return labels, centroids

    def _build_label_prototypes(self, label_clusters: Mapping[str, list[str]]) -> dict[str, list[float]]:
        prototypes: dict[str, list[float]] = {}
        for label_name, anchors in label_clusters.items():
            artefact = self._text_embedder.run(
                {
                    "id_artefatto_trascrizione": f"label::{label_name}",
                    "text": label_name,
                    "sentences": anchors,
                    "words": [],
                }
            )
            vectors = artefact.get("sentence_vect")
            if not isinstance(vectors, list) or not vectors:
                raise InferenceError(f"text embedder returned no vectors for label '{label_name}'")
            prototypes[label_name] = self._mean_vector(vectors)
        return prototypes

    def _map_clusters_to_labels(
        self, centroids: Sequence[Sequence[float]], prototypes: Mapping[str, Sequence[float]]
    ) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for cluster_id, centroid in enumerate(centroids):
            best_label = min(
                prototypes.items(),
                key=lambda item: self._squared_l2_distance(centroid, item[1]),
            )[0]
            mapping[cluster_id] = best_label
        return mapping

    def _project_for_visualization(
        self, vectors: list[list[float]]
    ) -> tuple[list[list[float]], list[float]]:
        if not vectors:
            return [], []
        dimensions = len(vectors[0])
        n_components = min(2, len(vectors), dimensions)
        if n_components <= 0:
            return [], []
        try:
            pca_mod = import_module("sklearn.decomposition")
            pca_cls = getattr(pca_mod, "PCA")
        except ImportError as exc:
            raise InferenceError("scikit-learn is required for LabelClusterer PCA projection") from exc

        model = pca_cls(n_components=n_components)
        projected_nd = model.fit_transform(vectors)
        projected = [
            [float(component) for component in row]
            for row in projected_nd.tolist()
        ]
        explained = [float(value) for value in model.explained_variance_ratio_.tolist()]
        return projected, explained

    @staticmethod
    def _mean_vector(vectors: list[Any]) -> list[float]:
        if not vectors:
            raise InferenceError("cannot compute mean of empty vectors")
        first = vectors[0]
        if not isinstance(first, list) or not first:
            raise InferenceError("label anchor vectors must be non-empty lists")
        width = len(first)
        sums = [0.0] * width
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != width:
                raise InferenceError("label anchor vectors must share the same shape")
            for index, value in enumerate(vector):
                try:
                    sums[index] += float(value)
                except (TypeError, ValueError) as exc:
                    raise InferenceError("label anchor vectors must be numeric") from exc
        count = float(len(vectors))
        return [value / count for value in sums]

    @staticmethod
    def _squared_l2_distance(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b):
            raise InferenceError("vector dimensionality mismatch while mapping labels")
        total = 0.0
        for va, vb in zip(a, b, strict=True):
            diff = float(va) - float(vb)
            total += diff * diff
        return total
