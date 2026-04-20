"""Text embedding model that batches text, sentences, and words through a provider."""

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
            "sentences": list[str],  # may be empty
            "words": list[str],      # may be empty
        }

    The provider is invoked once with the ordered batch
    ``[text, *sentences, *words]`` and must return a list of vectors of the
    same length (each vector a ``list[float]``). The result is then sliced
    back into the three groups and returned as an artefact dict.
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
        sentences = payload.get("sentences", [])
        words = payload.get("words", [])

        if not isinstance(artefact_id, str) or not artefact_id:
            raise ValidationError("id_artefatto_trascrizione is required")
        if not isinstance(text, str):
            raise ValidationError("text must be a string")
        if not isinstance(sentences, list):
            raise ValidationError("sentences must be a list")
        if not isinstance(words, list):
            raise ValidationError("words must be a list")

        batch: list[str] = [text, *sentences, *words]
        raw = self._provider.infer(self._model_name, batch)

        vectors = self._coerce_vectors(raw, expected=len(batch))

        text_vect = vectors[0]
        sentence_vect = vectors[1 : 1 + len(sentences)]
        words_vect = vectors[1 + len(sentences) :]

        return {
            "id_artefatto_trascrizione": artefact_id,
            "text": text,
            "text_vect": text_vect,
            "sentence": list(sentences),
            "sentence_vect": sentence_vect,
            "words": list(words),
            "words_vect": words_vect,
        }

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
