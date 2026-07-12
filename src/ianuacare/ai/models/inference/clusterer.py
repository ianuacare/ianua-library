"""Speaker clustering with K-Means."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

DEFAULT_NUM_SPEAKERS = 2


def _import_sklearn() -> tuple[Any, Any]:
    try:
        cluster_mod = import_module("sklearn.cluster")
        preprocessing_mod = import_module("sklearn.preprocessing")
    except ImportError as exc:
        raise InferenceError(
            "scikit-learn is required for SpeakerClusterer; install with pip install -e '.[audio]'"
        ) from exc
    return cluster_mod.KMeans, preprocessing_mod.normalize


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


class SpeakerClusterer(BaseAIModel):
    """Cluster speaker embeddings with K-Means."""

    def __init__(
        self,
        num_speakers: int = DEFAULT_NUM_SPEAKERS,
        random_state: int = 42,
    ) -> None:
        self._num_speakers = max(1, num_speakers)
        self._random_state = random_state

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

        k = _resolve_num_clusters(
            payload.get("num_speakers"),
            default=self._num_speakers,
            max_clusters=len(valid),
        )

        if k <= 1:
            cluster_labels = [0] * len(valid)
        else:
            kmeans_cls, normalize_cls = _import_sklearn()
            try:
                numpy_mod = import_module("numpy")
            except ImportError as exc:
                raise InferenceError("numpy is required for SpeakerClusterer") from exc

            matrix = numpy_mod.asarray(valid, dtype=numpy_mod.float64)
            matrix = normalize_cls(matrix, norm="l2")
            model = kmeans_cls(n_clusters=k, random_state=self._random_state, n_init="auto")
            cluster_labels = [int(label) for label in model.fit_predict(matrix).tolist()]

        return _map_labels_to_segments(vectors, cluster_labels)


def _resolve_num_clusters(value: Any, *, default: int, max_clusters: int) -> int:
    parsed = _parse_num_speakers(value)
    k = parsed if parsed is not None else default
    return max(1, min(k, max_clusters))


def _parse_num_speakers(value: Any) -> int | None:
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
