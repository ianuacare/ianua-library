"""InputDataParser."""

import pytest

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import InputDataParser


def test_parse_pass_through() -> None:
    p = DataPacket(validated_data={"x": 1})
    InputDataParser().parse(p)
    assert p.parsed_data == {"x": 1}


def test_parse_llm_payload() -> None:
    p = DataPacket(validated_data={"text": "hello world", "unused": "x"})
    InputDataParser().parse(p, model_key="llm")
    assert p.parsed_data == {"prompt": "", "text": "hello world"}


def test_parse_llm_requires_text() -> None:
    p = DataPacket(validated_data={"summary": "missing text"})
    with pytest.raises(ValidationError):
        InputDataParser().parse(p, model_key="llm")


def test_parse_diarization_payload() -> None:
    p = DataPacket(
        validated_data={
            "segments": [{"start": 0.0, "end": 1.0, "text": "ciao"}],
            "num_speakers": 2,
        }
    )
    InputDataParser().parse(p, model_key="diarization")
    assert p.parsed_data == {
        "segments": [{"start": 0.0, "end": 1.0, "text": "ciao"}],
        "num_speakers": 2,
    }


def test_parse_diarization_segments_default_to_empty_list() -> None:
    p = DataPacket(validated_data={})
    InputDataParser().parse(p, model_key="diarization")
    assert p.parsed_data == {"segments": []}


def test_parse_diarization_preserves_word_timestamp_fields() -> None:
    """Regression ianua-library#15: word_timestamps was silently dropped by the whitelist."""
    p = DataPacket(
        validated_data={
            "audio_path": "/tmp/a.mp3",
            "word_timestamps": True,
            "min_embedding_seconds": 1.0,
            "merge_max_gap_seconds": 0.5,
            "num_speakers": 2,
        }
    )
    InputDataParser().parse(p, model_key="diarization")
    assert p.parsed_data["word_timestamps"] is True
    assert p.parsed_data["min_embedding_seconds"] == 1.0
    assert p.parsed_data["merge_max_gap_seconds"] == 0.5


def test_parse_text_embedder_default_sentences_only() -> None:
    p = DataPacket(
        validated_data={
            "id_artefatto_trascrizione": "tr-1",
            "text": "  Prima frase. Seconda frase!  ",
        }
    )
    InputDataParser().parse(p, model_key="text_embedder")
    assert p.parsed_data == {
        "id_artefatto_trascrizione": "tr-1",
        "text": "Prima frase Seconda frase",
        "chunks": ["Prima frase Seconda frase"],
        "sentences": ["Prima frase Seconda frase"],
        "words": [],
    }


def test_parse_text_embedder_with_words() -> None:
    p = DataPacket(
        validated_data={
            "id_artefatto_trascrizione": "tr-2",
            "text": "ciao mondo",
            "split_sentences": False,
            "split_words": True,
        }
    )
    InputDataParser().parse(p, model_key="text_embedder")
    assert p.parsed_data == {
        "id_artefatto_trascrizione": "tr-2",
        "text": "ciao mondo",
        "chunks": ["ciao mondo"],
        "sentences": [],
        "words": ["ciao", "mondo"],
    }


def test_parse_text_embedder_lowercase_flag() -> None:
    p = DataPacket(
        validated_data={
            "id_artefatto_trascrizione": "tr-3",
            "text": "Ciao Mondo",
            "split_sentences": False,
            "lowercase": True,
        }
    )
    InputDataParser().parse(p, model_key="text_embedder")
    assert p.parsed_data["text"] == "ciao mondo"


def test_parse_text_embedder_remove_stopwords_flag() -> None:
    p = DataPacket(
        validated_data={
            "id_artefatto_trascrizione": "tr-4",
            "text": "Il paziente ha un dolore al braccio",
            "split_sentences": False,
            "remove_stopwords": True,
        }
    )
    InputDataParser().parse(p, model_key="text_embedder")
    assert p.parsed_data["text"] == "paziente ha dolore braccio"


def test_parse_text_embedder_requires_id() -> None:
    p = DataPacket(validated_data={"text": "ciao"})
    with pytest.raises(ValidationError):
        InputDataParser().parse(p, model_key="text_embedder")


def test_parse_text_embedder_requires_text() -> None:
    p = DataPacket(validated_data={"id_artefatto_trascrizione": "tr-x"})
    with pytest.raises(ValidationError):
        InputDataParser().parse(p, model_key="text_embedder")


def test_parse_text_embedder_rejects_non_mapping() -> None:
    p = DataPacket(validated_data="plain text")
    with pytest.raises(ValidationError):
        InputDataParser().parse(p, model_key="text_embedder")


def test_parse_text_embedder_chunks_long_text() -> None:
    p = DataPacket(
        validated_data={
            "id_artefatto_trascrizione": "tr-long",
            "text": "uno due tre quattro cinque sei.",
            "split_sentences": False,
        }
    )
    InputDataParser(max_tokens=3).parse(p, model_key="text_embedder")
    assert len(p.parsed_data["chunks"]) > 1
    assert p.parsed_data["text"] == "uno due tre quattro cinque sei"


def test_parse_text_embedder_rejects_invalid_max_tokens() -> None:
    with pytest.raises(ValidationError):
        InputDataParser(max_tokens=0)
