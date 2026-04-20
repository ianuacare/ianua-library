"""Emotion clustering model based on embedding vectors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.text_embedder import TextEmbedder
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

EMOTION_CLUSTERS: dict[str, list[str]] = {
    "depression": ["tristezza", "vuoto", "disperazione", "anedonia"],
    "anxiety": ["ansia", "paura", "preoccupazione", "panico"],
    "anger": ["rabbia", "frustrazione", "irritazione"],
    "shame_guilt": ["vergogna", "colpa", "indegnita"],
    "attachment_positive": ["amore", "fiducia", "connessione"],
    "attachment_negative": ["abbandono", "rifiuto", "gelosia"],
    "positive": ["gioia", "sollievo", "speranza"],
    "numbing": ["apatia", "distacco", "indifferenza"],
    "cognitive": ["confusione", "ruminazione", "dubbio"],
    "high_arousal": ["agitazione", "stress", "overwhelm"],
    "trauma": ["impotenza", "dissociazione", "flashback"],
}


class EmotionClusterer(BaseAIModel):
    """Cluster text embeddings and map discovered groups to emotion families."""

    def __init__(
        self,
        text_embedder: TextEmbedder | None = None,
        random_state: int = 42,
    ) -> None:
        self._text_embedder = text_embedder or TextEmbedder()
        self._random_state = random_state

    def run(self, payload: Any) -> dict[str, Any]:
        """Cluster input vectors then project them with PCA as final step."""
        vectors = self._extract_vectors(payload)
        n_clusters = min(len(vectors), len(EMOTION_CLUSTERS))
        if n_clusters == 0:
            return {
                "labels": [],
                "emotions": [],
                "cluster_to_emotion": {},
                "projected_vectors": [],
                "explained_variance_ratio": [],
            }

        labels, centroids = self._cluster_in_original_space(vectors, n_clusters)
        prototypes = self._build_emotion_prototypes()
        cluster_to_emotion = self._map_clusters_to_emotions(centroids, prototypes)
        emotions = [cluster_to_emotion[label] for label in labels]
        projected_vectors, explained_variance_ratio = self._project_for_visualization(vectors)
        return {
            "labels": labels,
            "emotions": emotions,
            "cluster_to_emotion": cluster_to_emotion,
            "projected_vectors": projected_vectors,
            "explained_variance_ratio": explained_variance_ratio,
        }

    def _extract_vectors(self, payload: Any) -> list[list[float]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("emotion_clusterer payload must be a mapping")
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

    def _cluster_in_original_space(
        self, vectors: list[list[float]], n_clusters: int
    ) -> tuple[list[int], list[list[float]]]:
        try:
            kmeans_mod = import_module("sklearn.cluster")
            kmeans_cls = getattr(kmeans_mod, "KMeans")
        except ImportError as exc:
            raise InferenceError("scikit-learn is required for EmotionClusterer clustering") from exc

        model = kmeans_cls(n_clusters=n_clusters, random_state=self._random_state, n_init="auto")
        labels_nd = model.fit_predict(vectors)
        labels = [int(label) for label in labels_nd.tolist()]
        centroids = [
            [float(component) for component in row]
            for row in model.cluster_centers_.tolist()
        ]
        return labels, centroids

    def _build_emotion_prototypes(self) -> dict[str, list[float]]:
        prototypes: dict[str, list[float]] = {}
        for emotion, anchors in EMOTION_CLUSTERS.items():
            artefact = self._text_embedder.run(
                {
                    "id_artefatto_trascrizione": f"emotion::{emotion}",
                    "text": emotion,
                    "sentences": anchors,
                    "words": [],
                }
            )
            vectors = artefact.get("sentence_vect")
            if not isinstance(vectors, list) or not vectors:
                raise InferenceError(f"text embedder returned no vectors for emotion '{emotion}'")
            prototypes[emotion] = self._mean_vector(vectors)
        return prototypes

    def _map_clusters_to_emotions(
        self, centroids: Sequence[Sequence[float]], prototypes: Mapping[str, Sequence[float]]
    ) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for cluster_id, centroid in enumerate(centroids):
            best_emotion = min(
                prototypes.items(),
                key=lambda item: self._squared_l2_distance(centroid, item[1]),
            )[0]
            mapping[cluster_id] = best_emotion
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
            raise InferenceError("scikit-learn is required for EmotionClusterer PCA projection") from exc

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
            raise InferenceError("emotion anchor vectors must be non-empty lists")
        width = len(first)
        sums = [0.0] * width
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != width:
                raise InferenceError("emotion anchor vectors must share the same shape")
            for index, value in enumerate(vector):
                try:
                    sums[index] += float(value)
                except (TypeError, ValueError) as exc:
                    raise InferenceError("emotion anchor vectors must be numeric") from exc
        count = float(len(vectors))
        return [value / count for value in sums]

    @staticmethod
    def _squared_l2_distance(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b):
            raise InferenceError("vector dimensionality mismatch while mapping emotions")
        total = 0.0
        for va, vb in zip(a, b, strict=True):
            diff = float(va) - float(vb)
            total += diff * diff
        return total
