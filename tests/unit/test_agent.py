"""Agent behavior through the real LLM wrapper, with deterministic model replies."""

import asyncio
import json
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest

from ianuacare.ai.models.inference.LLM import LLMModel
from ianuacare.ai.models.normalizer import ModelOutNormalizer
from ianuacare.ai.providers.base import AIProvider
from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.agent import Agent
from ianuacare.core.exceptions import AuthorizationError
from ianuacare.core.models import RequestContext, User
from ianuacare.core.retrieval import SemanticRetrieval
from ianuacare.core.tools import Tool

pytest.importorskip("jsonschema")

CONTEXT = RequestContext(User("reader", "reader", []), "test", {"scope": "a"})
SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
    "additionalProperties": False,
}


class ScriptedProvider(AIProvider):
    supports_tools = True

    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def infer(self, model_name, payload, *, model_type=None, params=None):
        self.requests.append((deepcopy(payload), deepcopy(params)))
        return next(self.replies)


def call(name="read", arguments='{"key":"item"}', id="call-1"):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": arguments}}


def make_agent(replies, tools=(), **kwargs):
    provider = ScriptedProvider(replies)
    llm = LLMModel(provider, "test", ModelOutNormalizer())
    return Agent(llm, tools, **kwargs), provider


async def read(arguments, context):
    return {"key": arguments["key"], "scope": context.metadata["scope"]}


def test_multi_step_tools_and_memory():
    tool = Tool("read", "Read a record", SCHEMA, read, read_only=True)
    agent, provider = make_agent(
        [
            {"tool_calls": [call(), call(id="call-2")]},
            {"tool_calls": [call(id="call-3")]},
            {"content": "answer"},
            {"content": "follow-up"},
        ],
        [tool],
        system_prompt="Be helpful",
        max_context_chars=10000,
    )

    async def run():
        result = await agent.arun("question", CONTEXT)
        assert result.finish_reason == "completed"
        assert result.text == "answer"
        results = [m for m in result.messages if m.role == "tool"]
        assert [m.tool_call_id for m in results] == ["call-1", "call-2", "call-3"]
        assert json.loads(results[0].content)["data"] == {"key": "item", "scope": "a"}
        await agent.arun("next", CONTEXT)

    asyncio.run(run())
    assert agent.state.turn_index == 2
    assert provider.requests[1][0][-1]["tool_call_id"] == "call-2"
    assert provider.requests[3][0][-2]["content"] == "answer"
    assert provider.requests[0][1]["tools"][0]["function"]["parameters"] == SCHEMA
    assert "reader" not in json.dumps(provider.requests[0][0])


def test_summary_keeps_system_and_compacts_whole_tool_turn():
    agent, provider = make_agent(
        [
            {"tool_calls": [call()]},
            {"content": "answer"},
            {"text": "Record a: item"},
            {"content": "next answer"},
            {"text": "Updated memory"},
        ],
        [Tool("read", "Read", SCHEMA, read)],
        system_prompt="System",
        max_context_chars=1,
    )

    async def run():
        await agent.arun("question", CONTEXT)
        assert agent.state.summary == "Record a: item"
        assert [m.role for m in agent.state.context] == ["system"]
        await agent.arun("next", CONTEXT)

    asyncio.run(run())
    summarized = json.loads(provider.requests[2][0][-1]["content"])
    assert [m["role"] for m in summarized["history"]] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert provider.requests[3][0][1]["content"] == "[CONTEXT SUMMARY]\nRecord a: item"
    assert agent.state.turn_index == 2


@pytest.mark.parametrize(
    "bad_call",
    [
        call(name="missing"),
        call(arguments="{"),
        call(arguments="[]"),
        call(arguments='{"key":42}'),
        call(arguments='{"key":"x","scope":"other"}'),
    ],
)
def test_bad_arguments_are_returned_to_model_without_execution(bad_call):
    async def forbidden(arguments, context):
        pytest.fail("Invalid tool call reached handler")

    agent, provider = make_agent(
        [
            {"tool_calls": [bad_call]},
            {"content": "corrected"},
        ],
        [Tool("read", "Read", SCHEMA, forbidden)],
    )
    assert asyncio.run(agent.arun("question", CONTEXT)).text == "corrected"
    assert json.loads(provider.requests[1][0][-1]["content"])["is_error"] is True


@pytest.mark.parametrize(
    "limit, reason", [("max_steps", "step_limit"), ("max_tool_calls", "tool_limit")]
)
def test_limits_do_not_commit_partial_turns(limit, reason):
    agent, _ = make_agent(
        [
            {"tool_calls": [call(), call(id="call-2")]},
        ],
        [Tool("read", "Read", SCHEMA, read)],
        **{limit: 1},
    )
    result = asyncio.run(agent.arun("question", CONTEXT))
    assert result.finish_reason == reason
    assert result.text == ""
    assert len([m for m in result.messages if m.role == "tool"]) == 2
    assert agent.state.context == []


def test_timeout_is_tool_error_and_cancellation_propagates():
    async def slow(arguments, context):
        await asyncio.sleep(10)

    tool = Tool("read", "Read", SCHEMA, slow)
    agent, provider = make_agent(
        [
            {"tool_calls": [call()]},
            {"content": "unavailable"},
        ],
        [tool],
        tool_timeout=0.001,
    )
    asyncio.run(agent.arun("question", CONTEXT))
    assert "timed out" in provider.requests[1][0][-1]["content"]

    async def cancelled(arguments, context):
        raise asyncio.CancelledError

    agent, _ = make_agent([{"tool_calls": [call()]}], [Tool("read", "", SCHEMA, cancelled)])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.arun("question", CONTEXT))
    assert not agent.state.context


@pytest.mark.parametrize("error", [RuntimeError("bug"), AuthorizationError("denied")])
def test_unexpected_and_authorization_errors_stop_execution(error):
    async def failed(arguments, context):
        raise error

    agent, _ = make_agent([{"tool_calls": [call()]}], [Tool("read", "", SCHEMA, failed)])
    with pytest.raises(type(error)):
        asyncio.run(agent.arun("question", CONTEXT))
    assert not agent.state.context


def test_instances_are_isolated_and_incomplete_answers_are_not_saved():
    first, _ = make_agent([{"content": "first"}])
    second, _ = make_agent([{"content": "truncated", "finish_reason": "length"}])
    asyncio.run(first.arun("one", CONTEXT))
    result = asyncio.run(second.arun("two", CONTEXT))
    assert result.finish_reason == "incomplete"
    assert second.state.context == []
    assert first.state.context[-1].content == "first"


def test_duplicate_tools_and_unsupported_provider():
    tool = Tool("read", "", SCHEMA, read)
    with pytest.raises(ValueError, match="Duplicate"):
        make_agent([], [tool, tool])
    agent = Agent(LLMModel(CallableProvider(), "test", ModelOutNormalizer()))
    with pytest.raises(NotImplementedError, match="support tool"):
        asyncio.run(agent.arun("question", CONTEXT))


def hit(id, score, text=None):
    return {"id": id, "score": score, "payload": {"source_text": text or id}}


def retrieval_for(batches, **kwargs):
    reader = Mock()
    reader.read_vector_search.side_effect = batches
    retrieval = SemanticRetrieval(
        reader,
        AsyncMock(return_value=[0.5]),
        collection="authorized_collection",
        filters={"level": "text", "scope": "a"},
        **kwargs,
    )
    return retrieval, reader


def test_semantic_pool_refresh_dedup_decay_and_pruning():
    retrieval, reader = retrieval_for(
        [
            [hit("a", 0.9), hit("a", 1.0), hit("b", 0.8)],
            [hit("b", 0.9, "updated")],
            [hit("c", 0.6)],
        ],
        score_decay=0.5,
        pool_max_size=2,
    )

    async def run():
        first = await retrieval.search("first", CONTEXT, turn=0)
        assert [p["id"] for p in first.data] == ["a", "b"]
        second = await retrieval.search("refine", CONTEXT, turn=0)
        assert second.data[0]["score"] == 1.0  # No decay for a second search in the same turn.
        assert second.data[1]["source_text"] == "updated"
        third = await retrieval.search("later", CONTEXT, turn=2)
        assert [p["id"] for p in third.data] == ["c", "a", "b"]
        assert third.data[1]["score"] == 0.25  # Includes turns with no search.
        assert [p.id for p in retrieval.state.retrieved_pool] == ["c", "a"]

    asyncio.run(run())
    kwargs = reader.read_vector_search.call_args.kwargs
    assert kwargs["context"] is CONTEXT
    assert kwargs["filters"] == {"level": "text", "scope": "a"}


def test_automatic_retrieval_survives_conversation_compaction():
    retrieval, reader = retrieval_for([[hit("source", 1.0)], []], score_decay=0.5)
    agent, provider = make_agent(
        [
            {"content": "first"},
            {"text": "summary"},
            {"content": "second"},
            {"text": "new summary"},
        ],
        retrieval=retrieval,
        max_context_chars=1,
    )

    async def run():
        await agent.arun("first question", CONTEXT)
        assert not agent.state.context
        assert len(retrieval.state.retrieved_pool) == 1
        await agent.arun("second question", CONTEXT)

    asyncio.run(run())
    assert reader.read_vector_search.call_count == 2
    for request, expected_score in [(provider.requests[0], 1.0), (provider.requests[2], 0.5)]:
        messages = request[0]
        assert messages[-2]["tool_calls"][0]["id"] == messages[-1]["tool_call_id"]
        result = json.loads(messages[-1]["content"])
        assert result["source"] == "authorized_collection"
        assert result["data"][0]["score"] == expected_score


def test_optional_retrieval_is_called_only_when_requested_by_model():
    retrieval, reader = retrieval_for([[hit("a", 1.0)]])
    agent, _ = make_agent(
        [
            {"content": "No search needed"},
            {"tool_calls": [call("search_context", '{"query":"find"}')]},
            {"content": "Found"},
        ],
        retrieval=retrieval,
        auto_retrieve=False,
    )

    async def run():
        await agent.arun("hello", CONTEXT)
        reader.read_vector_search.assert_not_called()
        await agent.arun("find", CONTEXT)

    asyncio.run(run())
    assert reader.read_vector_search.call_count == 1
    assert retrieval.state.retrieved_pool[0].turn == 1


def test_automatic_retrieval_counts_towards_tool_budget():
    retrieval, reader = retrieval_for([[hit("a", 1.0)]])
    agent, _ = make_agent(
        [
            {"tool_calls": [call("search_context", '{"query":"again"}')]},
        ],
        retrieval=retrieval,
        max_tool_calls=1,
    )
    result = asyncio.run(agent.arun("find", CONTEXT))
    assert result.finish_reason == "tool_limit"
    assert reader.read_vector_search.call_count == 1
    assert not agent.state.context


def test_failed_search_does_not_change_pool_and_instances_are_isolated():
    retrieval, _ = retrieval_for([[hit("a", 1.0)], RuntimeError("read failed")])
    other, _ = retrieval_for([])

    async def run():
        await retrieval.search("first", CONTEXT, turn=0)
        with pytest.raises(RuntimeError, match="read failed"):
            await retrieval.search("next", CONTEXT, turn=1)

    asyncio.run(run())
    assert retrieval.state.retrieved_pool[0].turn == 0
    assert not other.state.retrieved_pool


def test_events_cover_automatic_retrieval_and_do_not_leak_between_calls():
    retrieval, _ = retrieval_for([[hit("a", 1)], []])
    agent, _ = make_agent([{"content": "first"}, {"content": "second"}], retrieval=retrieval)
    events, later = [], []

    async def capture(event):
        events.append(event)

    async def capture_later(event):
        later.append(event)

    async def run():
        await agent.arun("first", CONTEXT, on_event=capture)
        await agent.arun("second", CONTEXT, on_event=capture_later)

    asyncio.run(run())
    assert [e.type for e in events] == ["tool_started", "tool_finished"]
    assert events[0].call_id == events[1].call_id == "retrieval_0"
    assert events[1].result.data[0]["source_text"] == "a"
    assert later[0].call_id == "retrieval_1"


def test_events_for_errors_and_skipped_calls_are_safe():
    async def broken(arguments, context):
        raise RuntimeError("secret database credentials")

    async def run():
        events = []

        async def capture(event):
            events.append(event)

        agent, _ = make_agent([{"tool_calls": [call()]}], [Tool("read", "", SCHEMA, broken)])
        with pytest.raises(RuntimeError):
            await agent.arun("question", CONTEXT, on_event=capture)
        assert [e.type for e in events] == ["tool_started", "tool_failed"]
        assert events[-1].error == "execution_failed"
        assert events[-1].result is None
        events.clear()
        agent, _ = make_agent([{"tool_calls": [call(), call(id="second")]}], max_tool_calls=1)
        await agent.arun("question", CONTEXT, on_event=capture)
        assert len(events) == 2
        assert all(e.skipped and e.type == "tool_failed" for e in events)

    asyncio.run(run())


@pytest.mark.parametrize("timeout", [False, True])
def test_tool_errors_and_timeouts_emit_failure_before_final_answer(timeout):
    from ianuacare.core.tools import ToolResult

    async def fail(arguments, context):
        if timeout:
            await asyncio.sleep(1)
        return ToolResult("private upstream error", is_error=True)

    events = []

    async def capture(event):
        events.append(event)

    agent, _ = make_agent(
        [{"tool_calls": [call()]}, {"content": "unavailable"}],
        [Tool("read", "", SCHEMA, fail)],
        tool_timeout=0.001,
    )
    result = asyncio.run(agent.arun("question", CONTEXT, on_event=capture))
    assert result.finish_reason == "completed"
    assert [event.type for event in events] == ["tool_started", "tool_failed"]
    assert events[0].call_id == events[1].call_id
    assert events[1].result is None
    assert events[1].error == ("timeout" if timeout else "tool_failed")
