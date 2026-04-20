"""Topic clustering model based on embedding vectors."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any

from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.text_embedder import TextEmbedder
from ianuacare.core.exceptions.errors import InferenceError, ValidationError

TOPIC_CLUSTERS: dict[str, list[str]] = {
    "relazioni_familiari": ["famiglia", "genitori", "madre", "padre", "fratelli"],
    "relazioni_sentimentali": ["partner", "coppia", "separazione", "tradimento", "intimita"],
    "amicizie_e_rete_sociale": ["amicizia", "gruppo", "supporto", "solitudine", "appartenenza"],
    "lavoro_e_carriera": ["lavoro", "carriera", "colleghi", "azienda", "burnout"],
    "studio_e_formazione": ["studio", "universita", "esami", "scuola", "formazione"],
    "economia_e_stabilita_materiale": ["denaro", "debiti", "spese", "stabilita", "sicurezza"],
    "salute_fisica_e_stile_di_vita": ["salute", "alimentazione", "attivita", "energia", "benessere"],
    "sonno_e_ritmi_quotidiani": ["sonno", "insonnia", "stanchezza", "routine", "ritmi"],
    "eventi_di_vita_e_transizioni": ["lutto", "trasferimento", "cambiamento", "transizione", "perdita"],
    "genitorialita_e_ruoli_di_cura": ["figli", "genitorialita", "cura", "responsabilita", "accudimento"],
    "confini_personali_e_conflitti": ["confini", "conflitto", "limiti", "discussione", "assertivita"],
    "autonomia_e_decisioni": ["decisione", "autonomia", "scelta", "dipendenza", "controllo"],
    "abitudini_e_comportamenti_disfunzionali": ["evitamento", "dipendenza", "impulsivita", "compulsione", "abitudine"],
    "valori_significato_e_spiritualita": ["valori", "significato", "spiritualita", "scopo", "senso"],
    "obiettivi_personali_e_progetti_futuri": ["obiettivi", "progetto", "futuro", "piano", "motivazione"],
    "tempo_libero_interessi_identita_personale": ["hobby", "interessi", "creativita", "identita", "tempo"],
    "contesto_sociale_culturale": ["cultura", "migrazione", "stigma", "comunita", "integrazione"],
    "uso_digitale_social_media": ["social", "digitale", "smartphone", "notifiche", "schermo"],
}

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ']+")
_ITALIAN_STOPWORDS = {
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


class TopicClusterer(BaseAIModel):
    """Cluster text embeddings and map clusters to thematic topic labels."""

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
        n_clusters = self._resolve_n_clusters(payload, len(vectors))
        labels, centroids = self._cluster_in_original_space(vectors, n_clusters)
        prototypes = self._build_topic_prototypes()
        cluster_to_topic = self._map_clusters_to_topics(centroids, prototypes)
        topics = [cluster_to_topic[label] for label in labels]
        ranked_clusters = self._build_ranked_clusters(labels, texts, cluster_to_topic)
        return {
            "labels": labels,
            "topics": topics,
            "cluster_to_topic": cluster_to_topic,
            "ranked_clusters": ranked_clusters,
        }

    def _extract_payload(self, payload: Any) -> tuple[list[list[float]], list[str]]:
        if not isinstance(payload, Mapping):
            raise ValidationError("topic_clusterer payload must be a mapping")
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

    def _resolve_n_clusters(self, payload: Any, vector_count: int) -> int:
        default_k = min(8, len(TOPIC_CLUSTERS), vector_count)
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
        return min(parsed_k, vector_count, len(TOPIC_CLUSTERS))

    def _cluster_in_original_space(
        self, vectors: list[list[float]], n_clusters: int
    ) -> tuple[list[int], list[list[float]]]:
        try:
            kmeans_mod = import_module("sklearn.cluster")
            kmeans_cls = getattr(kmeans_mod, "KMeans")
        except ImportError as exc:
            raise InferenceError("scikit-learn is required for TopicClusterer clustering") from exc

        model = kmeans_cls(n_clusters=n_clusters, random_state=self._random_state, n_init="auto")
        labels_nd = model.fit_predict(vectors)
        labels = [int(label) for label in labels_nd.tolist()]
        centroids = [
            [float(component) for component in row]
            for row in model.cluster_centers_.tolist()
        ]
        return labels, centroids

    def _build_topic_prototypes(self) -> dict[str, list[float]]:
        prototypes: dict[str, list[float]] = {}
        for topic, anchors in TOPIC_CLUSTERS.items():
            artefact = self._text_embedder.run(
                {
                    "id_artefatto_trascrizione": f"topic::{topic}",
                    "text": topic,
                    "sentences": anchors,
                    "words": [],
                }
            )
            vectors = artefact.get("sentence_vect")
            if not isinstance(vectors, list) or not vectors:
                raise InferenceError(f"text embedder returned no vectors for topic '{topic}'")
            prototypes[topic] = self._mean_vector(vectors)
        return prototypes

    def _map_clusters_to_topics(
        self, centroids: Sequence[Sequence[float]], prototypes: Mapping[str, Sequence[float]]
    ) -> dict[int, str]:
        mapping: dict[int, str] = {}
        for cluster_id, centroid in enumerate(centroids):
            best_topic = min(
                prototypes.items(),
                key=lambda item: self._squared_l2_distance(centroid, item[1]),
            )[0]
            mapping[cluster_id] = best_topic
        return mapping

    def _build_ranked_clusters(
        self, labels: list[int], texts: list[str], cluster_to_topic: Mapping[int, str]
    ) -> list[dict[str, Any]]:
        total = len(labels)
        by_cluster: dict[int, list[int]] = {}
        for idx, cluster_id in enumerate(labels):
            by_cluster.setdefault(cluster_id, []).append(idx)

        rows: list[dict[str, Any]] = []
        for cluster_id, indexes in by_cluster.items():
            cluster_texts = [texts[idx].strip() for idx in indexes if texts[idx].strip()]
            examples = cluster_texts[: self._max_examples]
            rows.append(
                {
                    "cluster_id": cluster_id,
                    "label": cluster_to_topic.get(cluster_id, "unknown"),
                    "count": len(indexes),
                    "percentage": len(indexes) / total if total else 0.0,
                    "examples": examples,
                    "keywords": self._extract_keywords(cluster_texts),
                }
            )
        rows.sort(key=lambda item: (int(item["count"]), -int(item["cluster_id"])), reverse=True)
        return rows

    def _extract_keywords(self, texts: Sequence[str]) -> list[str]:
        if not texts or self._max_keywords <= 0:
            return []
        bag: Counter[str] = Counter()
        for text in texts:
            for token in _TOKEN_RE.findall(text.lower()):
                if token in _ITALIAN_STOPWORDS or len(token) < 3:
                    continue
                bag[token] += 1
        return [word for word, _ in bag.most_common(self._max_keywords)]

    @staticmethod
    def _mean_vector(vectors: list[Any]) -> list[float]:
        if not vectors:
            raise InferenceError("cannot compute mean of empty vectors")
        first = vectors[0]
        if not isinstance(first, list) or not first:
            raise InferenceError("topic anchor vectors must be non-empty lists")
        width = len(first)
        sums = [0.0] * width
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != width:
                raise InferenceError("topic anchor vectors must share the same shape")
            for index, value in enumerate(vector):
                try:
                    sums[index] += float(value)
                except (TypeError, ValueError) as exc:
                    raise InferenceError("topic anchor vectors must be numeric") from exc
        count = float(len(vectors))
        return [value / count for value in sums]

    @staticmethod
    def _squared_l2_distance(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b):
            raise InferenceError("vector dimensionality mismatch while mapping topics")
        total = 0.0
        for va, vb in zip(a, b, strict=True):
            diff = float(va) - float(vb)
            total += diff * diff
        return total
