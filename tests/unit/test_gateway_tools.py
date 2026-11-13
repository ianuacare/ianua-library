"""Tool translation and the real agent cycle using deterministic immediate awaits."""

import json
from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from ianuacare import InferenceGatewayProvider, LLMModel, ModelOutNormalizer
from ianuacare.ai.providers.gateway_tools import messages_to_converse, tool_config
from ianuacare.core.agent import Agent
from ianuacare.core.chatbot.message import ConversationMemory, Message
from ianuacare.core.models import RequestContext, User
from ianuacare.core.tools import Tool, ToolResult

SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Find transcripts",
            "parameters": SCHEMA,
        },
    }
]
NATIVE = {
    "role": "assistant",
    "content": [
        {"reasoningContent": {"reasoningText": {"text": "private", "signature": "signed"}}},
        {"toolUse": {"toolUseId": "t1", "name": "search", "input": {"query": "sonno"}}},
        {"toolUse": {"toolUseId": "t2", "name": "search", "input": {"query": "umore"}}},
    ],
}


class Transport:
    def __init__(self, *messages):
        self.messages = list(messages)
        self.requests = []

    def __call__(self, request, *, timeout_seconds):
        self.requests.append(json.loads(request.body))
        message, reason = self.messages.pop(0)
        return (
            200,
            json.dumps(
                {
                    "model": "llm",
                    "status": "completed",
                    "provider": "bedrock",
                    "message": message,
                    "stop_reason": reason,
                }
            ).encode(),
            {},
        )


def provider(post, **kwargs):
    return InferenceGatewayProvider(
        "https://gateway.test", tool_models={"llm"}, post_fn=post, **kwargs
    )


def test_capabilities_are_per_alias_not_per_text_modality():
    client = provider(Transport())
    assert client.supports_tools and client.supports_tools_for("llm")
    assert not client.supports_tools_for("other-text-model")
    assert not client.supports_tools_for("query-embeddings")
    with pytest.raises(ValueError, match="not enabled"):
        client.infer("other-text-model", "hello", model_type="text", params={"tools": TOOLS})
    with pytest.raises(ValueError, match="not enabled"):
        client.infer("llm", ["hello"], model_type="embedding", params={"tools": TOOLS})


def test_request_and_response_translation_preserves_signed_blocks():
    post = Transport(
        (NATIVE, "tool_use"), ({"role": "assistant", "content": [{"text": "Done"}]}, "end_turn")
    )
    client = provider(post)
    result = client.infer("llm", [{"role": "user", "content": "Question"}], params={"tools": TOOLS})
    assert post.requests[0]["payload"]["tool_config"] == {
        "tools": [
            {
                "toolSpec": {
                    "name": "search",
                    "description": "Find transcripts",
                    "inputSchema": {"json": SCHEMA},
                }
            }
        ],
        "toolChoice": {"auto": {}},
    }
    assert "tools" not in post.requests[0]["params"]
    assert result["content"] == "" and result["finish_reason"] == "tool_calls"
    assert result["tool_calls"][0]["id"] == "t1"
    assistant = Message(
        "assistant",
        result["content"],
        tool_calls=result["tool_calls"],
        provider_metadata=result["provider_metadata"],
    )
    client.infer(
        "llm",
        [
            assistant.to_dict(),
            {"role": "tool", "tool_call_id": "t1", "content": "Found"},
            {"role": "tool", "tool_call_id": "t2", "content": '{"is_error":true}'},
        ],
        params={"tools": TOOLS},
    )
    sent = post.requests[1]["payload"]["messages"]
    assert sent[0] == NATIVE
    assert len(sent[1]["content"]) == 2
    assert sent[1]["content"][1]["toolResult"]["status"] == "error"


@pytest.mark.parametrize(
    "choice,expected",
    [
        ("auto", {"auto": {}}),
        ("required", {"any": {}}),
        ({"type": "function", "function": {"name": "search"}}, {"tool": {"name": "search"}}),
    ],
)
def test_tool_choice_translation(choice, expected):
    assert tool_config(TOOLS, choice)["toolChoice"] == expected


@pytest.mark.parametrize(
    "choice", ["none", "unknown", {"type": "function", "function": {"name": "missing"}}]
)
def test_unknown_tool_choice_is_rejected(choice):
    with pytest.raises(ValueError):
        tool_config(TOOLS, choice)


def test_strict_tools_are_not_silently_weakened():
    tools = deepcopy(TOOLS)
    tools[0]["function"]["strict"] = True
    with pytest.raises(ValueError, match="Strict"):
        tool_config(tools)


@pytest.mark.parametrize(
    "reason,expected", [("max_tokens", "length"), ("guardrail_intervened", "content_filter")]
)
def test_incomplete_response_reasons_are_not_mistaken_for_completed_answers(reason, expected):
    client = provider(Transport(({"role": "assistant", "content": [{"text": "Partial"}]}, reason)))
    assert client.infer("llm", "hello")["finish_reason"] == expected


def test_edited_or_cross_model_signed_history_is_rejected():
    result = provider(Transport((NATIVE, "tool_use"))).infer(
        "llm", "hello", params={"tools": TOOLS}
    )
    message = Message(
        "assistant",
        result["content"],
        tool_calls=result["tool_calls"],
        provider_metadata=result["provider_metadata"],
    ).to_dict()
    edited = deepcopy(message)
    edited["content"] = "edited"
    with pytest.raises(ValueError, match="edited"):
        messages_to_converse([edited], "llm")
    with pytest.raises(ValueError, match="different model"):
        messages_to_converse([message], "other")
    memory = ConversationMemory()
    memory.context = [Message(**message)]
    assert "provider_metadata" not in memory.summary_payload()["history"][0]
    assert memory.context[0].to_dict()["provider_metadata"] == message["provider_metadata"]


def test_invalid_tool_arguments_fail_before_http():
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "x",
                "type": "function",
                "function": {"name": "search", "arguments": "[]"},
            }
        ],
    }
    with pytest.raises(ValueError, match="JSON object"):
        provider(Transport()).infer("llm", [message], params={"tools": TOOLS})


def finish_immediately(coroutine):
    """Drive only immediate test awaits; never substitute a real event loop for I/O."""
    try:
        coroutine.send(None)
    except StopIteration as done:
        return done.value
    finally:
        coroutine.close()
    raise AssertionError("Test coroutine unexpectedly scheduled real I/O")


@pytest.fixture
def immediate_transport(monkeypatch):
    async def to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    @asynccontextmanager
    async def timeout(seconds):
        yield

    # Test the protocol/agent logic, without timers, threads or network sockets.
    monkeypatch.setattr("asyncio.to_thread", to_thread)
    monkeypatch.setattr("asyncio.timeout", timeout)


def test_real_agent_executes_tools_and_roundtrips_metadata(immediate_transport):
    post = Transport(
        (NATIVE, "tool_use"),
        ({"role": "assistant", "content": [{"text": "Answer"}]}, "end_turn"),
        ({"role": "assistant", "content": [{"text": "Next answer"}]}, "end_turn"),
    )
    fields = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}
    llm = LLMModel(
        provider(post),
        "llm",
        ModelOutNormalizer(),
        temperature=None,
        top_p=None,
        additional_model_fields=fields,
    )
    executed = []

    async def search(arguments, context):
        executed.append(arguments)
        return {"source": "transcript", "text": "Evidence"}

    class TestTool(Tool):
        async def call(self, arguments, context):
            # This test exercises orchestration, not optional JSON-schema validation.
            return ToolResult(await self.handler(arguments, context))

    tool = TestTool("search", "Find transcripts", SCHEMA, search)
    agent = Agent(llm, [tool], max_context_chars=100000)
    context = RequestContext(User("u", "reader", []), "test")
    result = finish_immediately(agent.arun("Question", context))
    assert result.text == "Answer" and result.finish_reason == "completed"
    assert executed == [{"query": "sonno"}, {"query": "umore"}]
    assert post.requests[1]["payload"]["messages"][1] == NATIVE
    assert result.messages[1].provider_metadata
    restored = Agent(llm, [tool], max_context_chars=100000)
    restored.state.context = [
        Message(**json.loads(json.dumps(m.to_dict()))) for m in agent.state.context
    ]
    followup = finish_immediately(restored.arun("Follow up", context))
    assert followup.text == "Next answer"
    assert all(request["params"]["additional_model_fields"] == fields for request in post.requests)
    assert post.requests[2]["payload"]["messages"][1] == NATIVE


def test_llm_rejects_wrong_alias_even_when_provider_has_other_tool_models(immediate_transport):
    llm = LLMModel(provider(Transport()), "other", ModelOutNormalizer())
    with pytest.raises(NotImplementedError):
        finish_immediately(llm.achat([], tools=TOOLS))
