"""OutputDataParser."""

import pytest

from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import OutputDataParser


def test_normalize_dict_result() -> None:
    p = DataPacket(inference_result={"summary": "ok", "score": 1})
    OutputDataParser().parse(p)
    assert p.processed_data == {"summary": "ok", "score": 1}
    assert p.processed_data is not p.inference_result


def test_normalize_non_dict_result() -> None:
    p = DataPacket(inference_result="plain text")
    OutputDataParser().parse(p, model_key="llm")
    assert p.processed_data == {"output": "plain text"}


def test_llm_without_schema_skips_validation() -> None:
    p = DataPacket(inference_result={"summary": "ok"})
    OutputDataParser().parse(p, model_key="llm")
    assert p.processed_data == {"summary": "ok"}


def test_llm_missing_required_field_raises() -> None:
    p = DataPacket(inference_result={"summary": "ok"})
    schema = {"required": ["summary", "score"]}
    with pytest.raises(ValidationError):
        OutputDataParser().parse(p, model_key="llm", schema=schema)


def test_llm_wrong_type_raises() -> None:
    p = DataPacket(inference_result={"summary": "ok", "score": "not-a-number"})
    schema = {
        "required": ["summary", "score"],
        "properties": {
            "summary": {"type": "string"},
            "score": {"type": "number"},
        },
    }
    with pytest.raises(ValidationError):
        OutputDataParser().parse(p, model_key="llm", schema=schema)


def test_llm_schema_coherent_passes() -> None:
    p = DataPacket(inference_result={"summary": "ok", "score": 0.87, "tags": ["a", "b"]})
    schema = {
        "required": ["summary", "score"],
        "properties": {
            "summary": {"type": "string"},
            "score": {"type": "number"},
            "tags": {"type": "array"},
        },
    }
    OutputDataParser().parse(p, model_key="llm", schema=schema)
    assert p.processed_data == {"summary": "ok", "score": 0.87, "tags": ["a", "b"]}


def test_llm_schema_boolean_not_integer() -> None:
    p = DataPacket(inference_result={"score": True})
    schema = {"properties": {"score": {"type": "integer"}}}
    with pytest.raises(ValidationError):
        OutputDataParser().parse(p, model_key="llm", schema=schema)


def test_llm_type_union() -> None:
    p = DataPacket(inference_result={"value": None})
    schema = {"properties": {"value": {"type": ["string", "null"]}}}
    OutputDataParser().parse(p, model_key="llm", schema=schema)
    assert p.processed_data == {"value": None}


def test_diarization_only_normalizes() -> None:
    p = DataPacket(inference_result={"segments": [{"start": 0.0, "end": 1.0}]})
    OutputDataParser().parse(p, model_key="diarization")
    assert p.processed_data == {"segments": [{"start": 0.0, "end": 1.0}]}


def test_text_embedder_wraps_single_artefact() -> None:
    artefact = {
        "id_artefatto_trascrizione": "tr-1",
        "text": "ciao",
        "text_vect": [1.0, 2.0],
        "sentence": [],
        "sentence_vect": [],
        "words": [],
        "words_vect": [],
    }
    p = DataPacket(inference_result=artefact)
    OutputDataParser().parse(p, model_key="text_embedder")
    assert p.processed_data == {"artefatti": [artefact]}


def test_text_embedder_passes_list_through() -> None:
    artefacts = [
        {"id_artefatto_trascrizione": "a", "text": "x"},
        {"id_artefatto_trascrizione": "b", "text": "y"},
    ]
    p = DataPacket(inference_result=artefacts)
    OutputDataParser().parse(p, model_key="text_embedder")
    assert p.processed_data == {"artefatti": artefacts}


def test_text_embedder_rejects_invalid_result() -> None:
    p = DataPacket(inference_result="not an artefact")
    with pytest.raises(ValidationError):
        OutputDataParser().parse(p, model_key="text_embedder")


def test_text_embedder_rejects_non_mapping_list_item() -> None:
    p = DataPacket(inference_result=[{"id_artefatto_trascrizione": "a"}, "bad"])
    with pytest.raises(ValidationError):
        OutputDataParser().parse(p, model_key="text_embedder")
