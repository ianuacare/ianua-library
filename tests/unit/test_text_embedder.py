"""TextEmbedder with CallableProvider."""

from __future__ import annotations

from typing import Any

import pytest

from ianuacare.ai.models.inference import TextEmbedder
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.exceptions.errors import InferenceError, ValidationError


def _fake_encoder(_: str, payload: Any) -> list[list[float]]:
    """Return a deterministic 2-dim vector for each string in the batch."""
    assert isinstance(payload, list)
    return [[float(len(item)), float(i)] for i, item in enumerate(payload)]


def _make_embedder() -> TextEmbedder:
    return TextEmbedder(
        provider=CallableProvider(_fake_encoder),
        model_name="test-embedder",
    )


class TestRun:
    def test_returns_artefact_with_all_levels(self) -> None:
        embedder = _make_embedder()
        payload = {
            "id_artefatto_trascrizione": "tr-1",
            "text": "ciao mondo",
            "sentences": ["ciao.", "mondo!"],
            "words": ["ciao", "mondo"],
        }
        result = embedder.run(payload)
        assert result["id_artefatto_trascrizione"] == "tr-1"
        assert result["text"] == "ciao mondo"
        assert result["sentence"] == ["ciao.", "mondo!"]
        assert result["words"] == ["ciao", "mondo"]
        assert result["text_vect"] == [10.0, 0.0]
        assert result["sentence_vect"] == [[5.0, 1.0], [6.0, 2.0]]
        assert result["words_vect"] == [[4.0, 3.0], [5.0, 4.0]]

    def test_handles_empty_sentences_and_words(self) -> None:
        embedder = _make_embedder()
        payload = {
            "id_artefatto_trascrizione": "tr-2",
            "text": "solo testo",
            "sentences": [],
            "words": [],
        }
        result = embedder.run(payload)
        assert result["text_vect"] == [10.0, 0.0]
        assert result["sentence"] == []
        assert result["sentence_vect"] == []
        assert result["words"] == []
        assert result["words_vect"] == []

    def test_defaults_missing_optional_fields(self) -> None:
        embedder = _make_embedder()
        payload = {"id_artefatto_trascrizione": "tr-3", "text": "x"}
        result = embedder.run(payload)
        assert result["sentence"] == []
        assert result["words"] == []

    def test_invokes_provider_with_single_batch(self) -> None:
        captured: list[Any] = []

        def capture(_: str, payload: Any) -> list[list[float]]:
            captured.append(payload)
            return [[1.0] for _ in payload]

        embedder = TextEmbedder(provider=CallableProvider(capture))
        embedder.run(
            {
                "id_artefatto_trascrizione": "tr-4",
                "text": "A",
                "sentences": ["B", "C"],
                "words": ["D"],
            }
        )
        assert captured == [["A", "B", "C", "D"]]


class TestValidation:
    def test_rejects_non_mapping_payload(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run("not a dict")

    def test_rejects_missing_id(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run({"text": "x"})

    def test_rejects_empty_id(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run({"id_artefatto_trascrizione": "", "text": "x"})

    def test_rejects_non_string_text(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run(
                {"id_artefatto_trascrizione": "tr", "text": 123}
            )

    def test_rejects_non_list_sentences(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run(
                {
                    "id_artefatto_trascrizione": "tr",
                    "text": "x",
                    "sentences": "not a list",
                }
            )

    def test_rejects_non_list_words(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedder().run(
                {
                    "id_artefatto_trascrizione": "tr",
                    "text": "x",
                    "words": "bad",
                }
            )


class TestProviderErrors:
    def test_rejects_non_list_provider_output(self) -> None:
        embedder = TextEmbedder(
            provider=CallableProvider(lambda _, __: "not a list"),
        )
        with pytest.raises(InferenceError):
            embedder.run({"id_artefatto_trascrizione": "tr", "text": "x"})

    def test_rejects_wrong_length_provider_output(self) -> None:
        embedder = TextEmbedder(
            provider=CallableProvider(lambda _, __: [[1.0]]),
        )
        with pytest.raises(InferenceError):
            embedder.run(
                {
                    "id_artefatto_trascrizione": "tr",
                    "text": "x",
                    "sentences": ["a", "b"],
                }
            )

    def test_rejects_non_numeric_components(self) -> None:
        embedder = TextEmbedder(
            provider=CallableProvider(lambda _, batch: [["nan-string"] for _ in batch]),
        )
        with pytest.raises(InferenceError):
            embedder.run({"id_artefatto_trascrizione": "tr", "text": "x"})

    def test_rejects_non_list_vector(self) -> None:
        embedder = TextEmbedder(
            provider=CallableProvider(lambda _, batch: ["not a vector" for _ in batch]),
        )
        with pytest.raises(InferenceError):
            embedder.run({"id_artefatto_trascrizione": "tr", "text": "x"})
