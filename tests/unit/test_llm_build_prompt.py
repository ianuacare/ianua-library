"""LLM ``build_prompt`` variants exposed by ``InputDataParser``."""

from ianuacare.core.models.packet import DataPacket
from ianuacare.core.orchestration.parser import InputDataParser


def test_text_only_prompt_is_empty() -> None:
    p = DataPacket(validated_data={"text": "hello"})
    InputDataParser().parse(p, model_key="llm")
    assert p.parsed_data["prompt"] == ""
    assert p.parsed_data["text"] == "hello"


def test_text_with_context_builds_prompt_with_sections() -> None:
    p = DataPacket(
        validated_data={"text": "What did the patient report?", "context": "ECG normal"}
    )
    InputDataParser().parse(p, model_key="llm")
    prompt = p.parsed_data["prompt"]
    assert "[CONTEXT]\nECG normal" in prompt
    assert "[QUESTION]\nWhat did the patient report?" in prompt
    assert p.parsed_data["context"] == "ECG normal"


def test_text_context_and_schema_serializes_schema_as_json() -> None:
    schema = {"type": "object", "required": ["summary"]}
    p = DataPacket(
        validated_data={
            "text": "Summarize.",
            "context": "Visit notes...",
            "schema": schema,
        }
    )
    InputDataParser().parse(p, model_key="llm")
    prompt = p.parsed_data["prompt"]
    assert "[CONTEXT]" in prompt
    assert "[SCHEMA]" in prompt
    assert '"required"' in prompt
    assert "[QUESTION]\nSummarize." in prompt
    assert p.parsed_data["schema"] == schema


def test_prompt_extras_are_appended_with_uppercase_labels() -> None:
    p = DataPacket(
        validated_data={
            "text": "Reply.",
            "context": "ctx",
            "prompt_extras": {"persona": "doctor", "constraints": "be brief"},
        }
    )
    InputDataParser().parse(p, model_key="llm")
    prompt = p.parsed_data["prompt"]
    assert "[PERSONA]\ndoctor" in prompt
    assert "[CONSTRAINTS]\nbe brief" in prompt
