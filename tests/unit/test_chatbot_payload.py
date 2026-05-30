"""Unit tests for Chatbot._build_llm_payload message list construction."""

from unittest.mock import MagicMock

from ianuacare.core.chatbot.chatbot import Chatbot
from ianuacare.core.chatbot.message import RetrievedPoint


def _make_bot(system_prompt: str | None = None) -> Chatbot:
    return Chatbot(
        reader=MagicMock(),
        writer=MagicMock(),
        llm=MagicMock(),
        collection="col",
        filters={},
        system_prompt=system_prompt,
    )


def _point(text: str, score: float = 0.9, turn: int = 0) -> RetrievedPoint:
    return RetrievedPoint(id="x", source_text=text, score=score, turn=turn)


def test_first_turn_no_system_no_retrieved() -> None:
    bot = _make_bot()
    msgs = bot._build_llm_payload("Hello?", [])
    assert len(msgs) == 1
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "Hello?"


def test_system_prompt_is_first_message() -> None:
    bot = _make_bot(system_prompt="You are an assistant.")
    msgs = bot._build_llm_payload("Hello?", [])
    assert msgs[0] == {"role": "system", "content": "You are an assistant."}
    assert msgs[-1]["role"] == "user"


def test_retrieved_snippets_injected_in_user_turn() -> None:
    bot = _make_bot()
    selected = [_point("Doc A"), _point("Doc B")]
    msgs = bot._build_llm_payload("Any info?", selected)
    user_content = msgs[-1]["content"]
    assert "[RETRIEVED CONTEXT]" in user_content
    assert "Doc A" in user_content
    assert "Doc B" in user_content
    assert "Any info?" in user_content


def test_summary_injected_before_retrieved() -> None:
    bot = _make_bot()
    bot.state.summary = "Previous summary here."
    selected = [_point("Doc X")]
    msgs = bot._build_llm_payload("Question?", selected)
    user_content = msgs[-1]["content"]
    assert "[CONTEXT SUMMARY]" in user_content
    summary_pos = user_content.index("[CONTEXT SUMMARY]")
    retrieved_pos = user_content.index("[RETRIEVED CONTEXT]")
    assert summary_pos < retrieved_pos


def test_prior_turns_preserved_in_history() -> None:
    bot = _make_bot(system_prompt="System.")
    # Simulate one completed turn
    bot.state.append_turn("First question", "First answer")
    msgs = bot._build_llm_payload("Second question?", [])
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "Second question?"


def test_empty_retrieved_snippets_not_injected() -> None:
    bot = _make_bot()
    selected = [_point("   ")]  # blank source_text
    msgs = bot._build_llm_payload("Q?", selected)
    assert "[RETRIEVED CONTEXT]" not in msgs[-1]["content"]
