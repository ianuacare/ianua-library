"""Text embedding model that batches text chunks, sentences, and words through a provider."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.models.inference.nlp import NLPModel
from ianuacare.ai.providers.base import AIProvider
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.exceptions.errors import InferenceError, ValidationError


class TextEmbedder(NLPModel):
    """Embed a document plus its sentence and word slices in a single batch.

    The model expects a payload already produced by
    :class:`ianuacare.core.orchestration.parser.InputDataParser` for the
    ``text_embedder`` key, i.e. a mapping with::

        {
            "id_artefatto_trascrizione": str,
            "text": str,
            "chunks": list[str],     # one chunk when text fits max_tokens
            "sentences": list[str],  # may be empty
            "words": list[str],      # may be empty
        }

    The provider is invoked once with the ordered batch
    ``[*chunks, *sentences, *words]`` and must return a list of vectors of the
    same length (each vector a ``list[float]``). The result is sliced back into
    the three groups; ``text_vect`` is the element-wise mean of the chunk
    vectors.
    """

    def __init__(
        self,
        provider: AIProvider | None = None,
        model_name: str = "text-embedder",
    ) -> None:
        super().__init__(provider or CallableProvider(), model_name)

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("text_embedder payload must be a mapping")

        artefact_id = payload.get("id_artefatto_trascrizione")
        text = payload.get("text")
        chunks = payload.get("chunks")
        sentences = payload.get("sentences", [])
        words = payload.get("words", [])

        if not isinstance(artefact_id, str) or not artefact_id:
            raise ValidationError("id_artefatto_trascrizione is required")
        if not isinstance(text, str):
            raise ValidationError("text must be a string")
        if chunks is None:
            chunks = [text] if text.strip() else []
        elif not isinstance(chunks, list):
            raise ValidationError("chunks must be a list")
        if not isinstance(sentences, list):
            raise ValidationError("sentences must be a list")
        if not isinstance(words, list):
            raise ValidationError("words must be a list")

        model_type_kw: str | None = None
        mt = payload.get("model_type")
        if isinstance(mt, str) and mt.strip():
            model_type_kw = mt.strip().lower()

        batch: list[str] = [*chunks, *sentences, *words]
        raw = self._provider.infer(
            self._model_name, batch, model_type=model_type_kw or "embedding"
        )

        vectors = self._coerce_vectors(raw, expected=len(batch))

        chunks_vect = vectors[: len(chunks)]
        sentence_vect = vectors[len(chunks) : len(chunks) + len(sentences)]
        words_vect = vectors[len(chunks) + len(sentences) :]

        return {
            "id_artefatto_trascrizione": artefact_id,
            "text": text,
            "text_vect": self._mean_vectors(chunks_vect),
            "chunks": list(chunks),
            "chunks_vect": chunks_vect,
            "sentence": list(sentences),
            "sentence_vect": sentence_vect,
            "words": list(words),
            "words_vect": words_vect,
        }

    @staticmethod
    def _mean_vectors(vectors: list[list[float]]) -> list[float]:
        """Return the element-wise mean of ``vectors`` (``[]`` when empty)."""
        if not vectors:
            return []
        dimension = len(vectors[0])
        totals = [0.0] * dimension
        for vector in vectors:
            for index in range(dimension):
                totals[index] += vector[index]
        count = float(len(vectors))
        return [total / count for total in totals]

    @staticmethod
    def _coerce_vectors(raw: Any, *, expected: int) -> list[list[float]]:
        """Normalize the provider output into a ``list[list[float]]`` of length ``expected``."""
        if not isinstance(raw, list):
            raise InferenceError("text_embedder provider must return a list of vectors")
        if len(raw) != expected:
            raise InferenceError(
                f"text_embedder provider returned {len(raw)} vectors, expected {expected}"
            )
        coerced: list[list[float]] = []
        for index, vector in enumerate(raw):
            if not isinstance(vector, list):
                raise InferenceError(f"vector at index {index} is not a list")
            try:
                coerced.append([float(component) for component in vector])
            except (TypeError, ValueError) as exc:
                raise InferenceError(
                    f"vector at index {index} contains non-numeric components"
                ) from exc
        return coerced
