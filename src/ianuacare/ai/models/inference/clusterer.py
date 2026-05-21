"""Speaker clustering with agglomerative clustering and optional Silhouette k selection."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ianuacare.ai._numeric import to_positive_int
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, ValidationError


def _import_sklearn() -> tuple[Any, Any, Any]:
    try:
        cluster_mod = import_module("sklearn.cluster")
        metrics_mod = import_module("sklearn.metrics")
        preprocessing_mod = import_module("sklearn.preprocessing")
    except ImportError as exc:
        raise InferenceError(
            "scikit-learn is required for SpeakerClusterer; install with pip install -e '.[audio]'"
        ) from exc
    agglomerative_cls = cluster_mod.AgglomerativeClustering
    silhouette_fn = metrics_mod.silhouette_score
    normalize_cls = preprocessing_mod.normalize
    return agglomerative_cls, silhouette_fn, normalize_cls


def _coerce_vectors(raw_vectors: Any) -> list[list[float]]:
    if not isinstance(raw_vectors, list):
        raise ValidationError("vectors must be a list")
    vectors: list[list[float]] = []
    for row_index, vector in enumerate(raw_vectors):
        if not isinstance(vector, list) or not vector:
            vectors.append([])
            continue
        try:
            vectors.append([float(component) for component in vector])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"vector at index {row_index} contains non-numeric components"
            ) from exc
    return vectors


def _valid_vectors(vectors: list[list[float]]) -> list[list[float]]:
    return [vector for vector in vectors if vector]


def _select_k_silhouette(
    matrix: Any,
    *,
    min_speakers: int,
    max_speakers: int,
    agglomerative_cls: Any,
    silhouette_fn: Any,
) -> int:
    n_samples = int(matrix.shape[0])
    if n_samples < 2:
        return 1

    lower = max(2, min_speakers)
    upper = min(max_speakers, n_samples)
    if lower > upper:
        return max(1, min(n_samples, min_speakers))

    best_k = lower
    best_score = float("-inf")
    for k in range(lower, upper + 1):
        if k >= n_samples:
            break
        model = agglomerative_cls(n_clusters=k, metric="cosine", linkage="average")
        labels = model.fit_predict(matrix)
        unique = {int(label) for label in labels.tolist()}
        if len(unique) < 2:
            continue
        score = float(silhouette_fn(matrix, labels, metric="cosine"))
        if score > best_score:
            best_score = score
            best_k = k
    return best_k


class SpeakerClusterer(BaseAIModel):
    """Cluster speaker embeddings; estimate k with Silhouette when ``num_speakers`` is unset."""

    def run(self, payload: Any) -> list[int]:
        if not isinstance(payload, dict):
            return []

        vectors = _coerce_vectors(payload.get("vectors"))
        n_segments = len(vectors)
        if n_segments == 0:
            return []

        valid = _valid_vectors(vectors)
        if not valid:
            return [0] * n_segments

        num_speakers = _parse_optional_num_speakers(payload.get("num_speakers"))
        min_speakers = to_positive_int(payload.get("min_speakers"), default=2, minimum=2)
        max_speakers = to_positive_int(payload.get("max_speakers"), default=6, minimum=2)
        if max_speakers < min_speakers:
            max_speakers = min_speakers

        agglomerative_cls, silhouette_fn, normalize_cls = _import_sklearn()
        try:
            numpy_mod = import_module("numpy")
        except ImportError as exc:
            raise InferenceError("numpy is required for SpeakerClusterer") from exc

        matrix = numpy_mod.asarray(valid, dtype=numpy_mod.float64)
        matrix = normalize_cls(matrix, norm="l2")

        if num_speakers is None:
            k = _select_k_silhouette(
                matrix,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                agglomerative_cls=agglomerative_cls,
                silhouette_fn=silhouette_fn,
            )
        else:
            k = max(1, min(num_speakers, len(valid)))

        if k <= 1:
            cluster_labels = [0] * len(valid)
        else:
            model = agglomerative_cls(n_clusters=k, metric="cosine", linkage="average")
            cluster_labels = [int(label) for label in model.fit_predict(matrix).tolist()]

        return _map_labels_to_segments(vectors, cluster_labels)


def _parse_optional_num_speakers(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return max(1, int(value))
    if isinstance(value, int):
        return max(1, value) if value >= 1 else None
    if isinstance(value, float):
        parsed = int(value)
        return max(1, parsed) if parsed >= 1 else None
    try:
        parsed = int(float(str(value).strip()))
        return max(1, parsed) if parsed >= 1 else None
    except (ValueError, TypeError):
        return None


def _map_labels_to_segments(
    vectors: list[list[float]],
    cluster_labels: list[int],
) -> list[int]:
    """Assign cluster ids; empty embeddings map to speaker 0."""
    labels: list[int] = []
    label_index = 0
    last_label = 0
    for vector in vectors:
        if not vector:
            labels.append(last_label)
            continue
        if label_index >= len(cluster_labels):
            labels.append(0)
            continue
        assigned = cluster_labels[label_index]
        labels.append(assigned)
        last_label = assigned
        label_index += 1
    return labels
