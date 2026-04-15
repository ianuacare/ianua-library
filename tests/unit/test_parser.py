"""DataParser."""

import pytest

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import DataParser


def test_parse_pass_through() -> None:
    p = DataPacket(validated_data={"x": 1})
    DataParser().parse(p)
    assert p.parsed_data == {"x": 1}


def test_parse_llm_payload() -> None:
    p = DataPacket(validated_data={"text": "hello world", "unused": "x"})
    DataParser().parse(p, model_key="llm")
    assert p.parsed_data == {"prompt": "", "text": "hello world"}


def test_parse_llm_requires_text() -> None:
    p = DataPacket(validated_data={"summary": "missing text"})
    with pytest.raises(ValidationError):
        DataParser().parse(p, model_key="llm")


def test_parse_diarization_payload() -> None:
    p = DataPacket(
        validated_data={
            "segments": [{"start": 0.0, "end": 1.0, "text": "ciao"}],
            "num_speakers": 2,
        }
    )
    DataParser().parse(p, model_key="diarization")
    assert p.parsed_data == {
        "segments": [{"start": 0.0, "end": 1.0, "text": "ciao"}],
        "num_speakers": 2,
    }


def test_parse_diarization_segments_default_to_empty_list() -> None:
    p = DataPacket(validated_data={})
    DataParser().parse(p, model_key="diarization")
    assert p.parsed_data == {"segments": []}
