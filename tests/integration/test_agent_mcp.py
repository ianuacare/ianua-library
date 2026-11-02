"""Real MCP protocol with injected in-memory readers; no external services."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp import Client, StdioServerParameters
from mcp.shared.exceptions import MCPError

from ianuacare.core.exceptions import AuthorizationError
from ianuacare.core.models import RequestContext, User
from ianuacare.core.tools import Tool
from ianuacare.infrastructure.mcp import create_structured_data_server, mcp_tools

SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
    "additionalProperties": False,
}


def context(scope):
    return RequestContext(User("reader", "reader", []), "test", {"scope": scope})


def server_for(resolver, calls):
    async def read(arguments, ctx):
        calls.append(ctx.metadata["scope"])
        records = {"a": {"item": "first"}, "b": {"item": "second"}}
        return {"value": records[ctx.metadata["scope"]][arguments["key"]], "source": "record"}

    return create_structured_data_server(
        [
            Tool("read", "Read a record", SCHEMA, read, read_only=True),
        ],
        resolver,
    )


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_discovery_execution_and_context_resolution_per_call(mode):
    scopes = iter(["a", "b"])
    calls = []

    async def resolve(ctx):
        return context(next(scopes))

    async def run():
        client = Client(server_for(resolve, calls), mode=mode)
        async with mcp_tools(client, namespace="data", allow={"read"}) as tools:
            assert [t.name for t in tools] == ["data__read"]
            assert "context" not in tools[0].input_schema["properties"]
            first = await tools[0].call({"key": "item"}, context("untrusted-local"))
            second = await tools[0].call({"key": "item"}, context("untrusted-local"))
            assert first.data["data"]["value"] == "first"
            assert second.data["data"]["value"] == "second"
            assert first.source == "data/read"
            assert first.is_error is False
        with pytest.raises((RuntimeError, MCPError)):
            await client.list_tools()

    asyncio.run(run())
    assert calls == ["a", "b"]


@pytest.mark.parametrize("denied", [True, False])
def test_missing_or_denied_context_never_reaches_repository(denied):
    calls = []

    async def resolve(ctx):
        if denied:
            raise AuthorizationError("private detail")
        return None

    async def run():
        async with Client(server_for(resolve, calls)) as client:
            await client.list_tools()
            result = await client.call_tool("read", {"key": "item"})
            assert result.is_error
            assert "private detail" not in json.dumps(result.structured_content)

    asyncio.run(run())
    assert calls == []


def test_validation_prevents_reader_call_and_discovery_failure_closes_client():
    calls = []

    async def resolve(ctx):
        return context("a")

    async def run():
        server = server_for(resolve, calls)
        async with Client(server) as client:
            await client.list_tools()
            result = await client.call_tool("read", {"key": 1})
            assert result.is_error
        client = Client(server)
        rejected = False
        try:
            async with mcp_tools(client, namespace="data", allow={"missing"}):
                pytest.fail("Discovery should fail")
        except* ValueError:
            # SDK task groups wrap exceptions raised inside a client context.
            rejected = True
        assert rejected
        with pytest.raises((RuntimeError, MCPError)):
            await client.list_tools()

    asyncio.run(run())
    assert calls == []


def test_server_rejects_tools_not_declared_read_only():
    async def handler(arguments, ctx):
        return {}

    async def resolve(ctx):
        return context("a")

    with pytest.raises(ValueError, match="read-only"):
        create_structured_data_server([Tool("write", "", SCHEMA, handler)], resolve)


def test_stdio_documented_server(tmp_path):
    # Exercise the runnable example rather than maintain a second demo server.
    root = Path(__file__).resolve().parents[2]
    example = (root / "docs/agent.md").read_text(encoding="utf-8")
    code = example.split("```python\n")[-1].split("```", 1)[0]
    script = tmp_path / "server.py"
    script.write_text(code, encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        env={**os.environ, "PYTHONPATH": str(root / "src")},
    )

    async def run():
        async with mcp_tools(Client(params), namespace="data") as tools:
            result = await tools[0].call({"key": "example"}, context("ignored"))
            assert result.data["data"]["record"] == {"value": 42}

    asyncio.run(run())


def test_streamable_http():
    import httpx2
    from mcp.client.streamable_http import streamable_http_client

    async def resolve(ctx):
        return context("a")

    async def run():
        server = server_for(resolve, [])
        app = server.streamable_http_app(stateless_http=True, json_response=True)
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
            ) as http,
        ):
            transport = streamable_http_client("http://localhost:8000/mcp", http_client=http)
            async with mcp_tools(Client(transport), namespace="data") as tools:
                result = await tools[0].call({"key": "item"}, context("ignored"))
                assert result.data["data"]["value"] == "first"

    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get("PUBMED_MCP_SOURCE"), reason="PubMed checkout not supplied")
def test_agent_with_existing_pubmed_server(monkeypatch):
    import httpx

    from ianuacare import CallableProvider, LLMModel, ModelOutNormalizer
    from ianuacare.core.agent import Agent

    source = Path(os.environ["PUBMED_MCP_SOURCE"])
    monkeypatch.syspath_prepend(str(source / "src"))
    from ianua_pubmed_mcp.config import Settings
    from ianua_pubmed_mcp.server import create_server

    requests = []

    def ncbi(request):
        requests.append(request.url.path)
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(
                200,
                json={
                    "esearchresult": {"count": "1", "idlist": ["9500320"]},
                },
            )
        return httpx.Response(
            200,
            text=(source / "tests/fixtures/efetch_retracted_9500320.xml").read_text(
                encoding="utf-8"
            ),
        )

    class ScriptedProvider(CallableProvider):
        supports_tools = True

    def reply(name, args, id):
        return {
            "tool_calls": [
                {
                    "id": id,
                    "type": "function",
                    "function": {
                        "name": f"pubmed__{name}",
                        "arguments": json.dumps(args),
                    },
                }
            ]
        }

    responses = iter(
        [
            reply("pubmed_search_articles", {"query": "example", "max_results": 1}, "search"),
            reply("pubmed_fetch_articles", {"pmids": ["9500320"]}, "fetch"),
            {"content": "Article 9500320 is retracted."},
        ]
    )
    llm = LLMModel(
        ScriptedProvider(lambda model, payload: next(responses)), "test", ModelOutNormalizer()
    )

    async def run():
        server = create_server(Settings(_env_file=None), ncbi_transport=httpx.MockTransport(ncbi))
        async with mcp_tools(
            Client(server),
            namespace="pubmed",
            allow={
                "pubmed_search_articles",
                "pubmed_fetch_articles",
            },
        ) as tools:
            events = []

            async def capture(event):
                events.append(event)

            result = await Agent(llm, tools, max_context_chars=100000).arun(
                "Search", context("a"), on_event=capture
            )
            assert [(event.type, event.call_id) for event in events] == [
                ("tool_started", "search"),
                ("tool_finished", "search"),
                ("tool_started", "fetch"),
                ("tool_finished", "fetch"),
            ]
            assert events[-1].result.data["articles"][0]["pmid"] == "9500320"
            assert result.finish_reason == "completed"
            fetched = json.loads([m.content for m in result.messages if m.role == "tool"][-1])
            assert fetched["data"]["articles"][0]["pmid"] == "9500320"
            assert fetched["data"]["articles"][0]["notices"]["is_retracted"] is True

    asyncio.run(run())
    assert len(requests) == 2
