"""Generic ranked label clustering model based on embedding vectors."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.text_embedder import TextEmbedder
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']+")
_DEFAULT_STOPWORDS = {
    "a",
    "ad",
    "al",
    "alla",
    "anche",
    "che",
    "con",
    "da",
    "del",
    "della",
    "di",
    "e",
    "ho",
    "il",
    "in",
    "io",
    "la",
    "le",
    "ma",
    "mi",
    "non",
    "per",
    "piu",
    "poi",
    "se",
    "sono",
    "su",
    "tra",
    "un",
    "una",
}


class RankedLabelClusterer(BaseAIModel):
    """Cluster vectors, map labels, and rank clusters by numerosity."""

    def __init__(
        self,
        text_embedder: TextEmbedder | None = None,
        random_state: int = 42,
        max_examples: int = 5,
        max_keywords: int = 5,
    ) -> None:
        self._text_embedder = text_embedder or TextEmbedder()
        self._random_state = random_state
        self._max_examples = max_examples
        self._max_keywords = max_keywords

    def run(self, payload: Any) -> dict[str, Any]:
        vectors, texts = self._extract_payload(payload)
        label_clusters = self._extract_label_clusters(payload)
        stopwords = self._extract_stopwords(payload)
        n_clusters = self._resolve_n_clusters(payload, len(vectors), len(label_clusters))
        labels, centroids = self._cluster_in_original_space(vectors, n_clusters)
        prototypes = self._build_label_prototypes(label_clusters)
        cluster_to_label = self._map_clusters_to_labels(centroids, prototypes)
        assigned_labels = [cluster_to_label[label] for label in labels]
        ranked_clusters = self._build_ranked_clusters(labels, texts, cluster_to_label, stopwords)
        return {
            "labels": labels,
            "assigned_labels": assigned_labels,
            "cluster_to_label": cluster_to_label,
            "ranked_clusters": ranked_clusters,
        }

    def _extract_payload(self, payload: Any) -> tuple[list[list[float]], list[str]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("ranked_label_clusterer payload must be a mapping")
        raw_vectors = payload.get("vectors")
        if not isinstance(raw_vectors, list) or not raw_vectors:
            raise ValidationError("vectors must be a non-empty list")

        vectors: list[list[float]] = []
        for row_index, vector in enumerate(raw_vectors):
            if not isinstance(vector, list) or not vector:
                raise ValidationError(f"vector at index {row_index} must be a non-empty list")
            try:
                vectors.append([float(component) for component in vector])
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"vector at index {row_index} contains non-numeric components"
                ) from exc
        width = len(vectors[0])
        if any(len(vector) != width for vector in vectors):
            raise ValidationError("all vectors must have the same dimensionality")

        raw_texts = payload.get("texts", [])
        if not isinstance(raw_texts, list):
            raise ValidationError("texts must be a list when provided")
        texts: list[str] = []
        for index, value in enumerate(raw_texts):
            if not isinstance(value, str):
                raise ValidationError(f"text at index {index} must be a string")
            texts.append(value)
        if texts and len(texts) != len(vectors):
            raise ValidationError("texts length must match vectors length")
        if not texts:
            texts = [""] * len(vectors)
        return vectors, texts

    def _extract_label_clusters(self, payload: Any) -> dict[str, list[str]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("ranked_label_clusterer payload must be a mapping")
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

    def _resolve_n_clusters(self, payload: Any, vector_count: int, label_count: int) -> int:
        default_k = min(8, label_count, vector_count)
        if not isinstance(payload, Mapping):
            return max(1, default_k)
        raw_k = payload.get("num_clusters")
        if raw_k is None:
            return max(1, default_k)
        try:
            parsed_k = int(raw_k)
        except (TypeError, ValueError) as exc:
            raise ValidationError("num_clusters must be an integer when provided") from exc
        if parsed_k <= 0:
            raise ValidationError("num_clusters must be > 0")
        return min(parsed_k, vector_count, label_count)

    def _cluster_in_original_space(
        self, vectors: list[list[float]], n_clusters: int
    ) -> tuple[list[int], list[list[float]]]:
        try:
            kmeans_mod = import_module("sklearn.cluster")
            kmeans_cls = getattr(kmeans_mod, "KMeans")
        except ImportError as exc:
            raise InferenceError("scikit-learn is required for RankedLabelClusterer clustering") from exc

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
        for label, anchors in label_clusters.items():
            artefact = self._text_embedder.run(
                {
                    "id_artefatto_trascrizione": f"label::{label}",
                    "text": label,
                    "sentences": anchors,
                    "words": [],
                }
            )
            vectors = artefact.get("sentence_vect")
            if not isinstance(vectors, list) or not vectors:
                raise InferenceError(f"text embedder returned no vectors for label '{label}'")
            prototypes[label] = self._mean_vector(vectors)
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

    def _build_ranked_clusters(
        self,
        labels: list[int],
        texts: list[str],
        cluster_to_label: Mapping[int, str],
        stopwords: set[str],
    ) -> list[dict[str, Any]]:
        total = len(labels)
        by_cluster: dict[int, list[int]] = {}
        for idx, cluster_id in enumerate(labels):
            by_cluster.setdefault(cluster_id, []).append(idx)

        rows: list[dict[str, Any]] = []
        for cluster_id, indexes in by_cluster.items():
            cluster_texts = [texts[idx].strip() for idx in indexes if texts[idx].strip()]
            rows.append(
                {
                    "cluster_id": cluster_id,
                    "label": cluster_to_label.get(cluster_id, "unknown"),
                    "count": len(indexes),
                    "percentage": len(indexes) / total if total else 0.0,
                    "examples": cluster_texts[: self._max_examples],
                    "keywords": self._extract_keywords(cluster_texts, stopwords),
                }
            )
        rows.sort(key=lambda item: (int(item["count"]), -int(item["cluster_id"])), reverse=True)
        return rows

    def _extract_keywords(self, texts: Sequence[str], stopwords: set[str]) -> list[str]:
        if not texts or self._max_keywords <= 0:
            return []
        bag: Counter[str] = Counter()
        for text in texts:
            for token in _TOKEN_RE.findall(text.lower()):
                if token in stopwords or len(token) < 3:
                    continue
                bag[token] += 1
        return [word for word, _ in bag.most_common(self._max_keywords)]

    @staticmethod
    def _extract_stopwords(payload: Any) -> set[str]:
        if not isinstance(payload, Mapping):
            return set(_DEFAULT_STOPWORDS)
        raw = payload.get("stopwords")
        if raw is None:
            return set(_DEFAULT_STOPWORDS)
        if not isinstance(raw, list):
            raise ValidationError("stopwords must be a list of strings when provided")
        stopwords: set[str] = set()
        for idx, item in enumerate(raw):
            if not isinstance(item, str):
                raise ValidationError(f"stopwords[{idx}] must be a string")
            stopwords.add(item.lower())
        return stopwords

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
