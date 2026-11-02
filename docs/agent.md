# Conversational agent and MCP

Install `ianuacare[agent,together]` for local tools or `ianuacare[mcp,together]`
for MCP. The base package still has no mandatory dependencies.

`Agent` owns one conversation's history and rolling summary, using the same
`ConversationMemory` as `Chatbot`. Create a separate agent for each authorized
conversation; never share its state across users or patient scopes. The application
owns persistence of `agent.state.context`, `summary`, and `turn_index`.

The agent knows only tool descriptions and schemas. A handler can read an ordinary
database, query a vector index, or call another service. Database schemas, permission
checks and semantic ranking belong to the application's handlers. Results are not
automatically embedded or reranked.

## A local tool

```python
from ianuacare.core.agent import Agent
from ianuacare.core.tools import Tool

# repository and llm are supplied by the application.
async def read_record(arguments, context):
    return await repository.read(
        key=arguments["key"], user=context.user, scope=context.metadata["scope"]
    )

reader = Tool(
    name="read_record",
    description="Read a record by key within the authorized scope.",
    input_schema={
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "required": ["key"],
        "additionalProperties": False,
    },
    handler=read_record,
    read_only=True,
)
agent = Agent(llm, [reader], system_prompt="Use the available sources to answer.")
result = await agent.arun("Read the record named example", request_context)
if result.finish_reason == "completed":
    print(result.text)
```

`RequestContext` is passed to handlers, never automatically included in the prompt.
Handlers must return JSON-serializable data, optionally a `ToolResult` carrying
`source` and `is_error`. Raise `ValidationError` for safe, actionable input errors;
unexpected exceptions and local authorization errors abort the run. Validation
errors and timeouts become tool results that the model can respond to. Tools are
executed sequentially, without automatic retries.

## Per-run activity events

Pass an async callback to `await agent.arun(query, context, on_event=on_event)`.
The callback receives `AgentEvent` values from the same execution path for automatic
retrieval, local tools and MCP tools. It belongs only to that invocation and is never
stored on the shared agent instance.

```python
async def on_event(event):
    # Project only application-approved fields before sending to a UI or audit log.
    print(event.type, event.call_id, event.tool_name)

result = await agent.arun("Find relevant sources", request_context, on_event=on_event)
```

Events contain `call_id`, `tool_name` and parsed `arguments` (or `None` for invalid
arguments). `tool_started` precedes execution; `tool_finished` carries a successful
`ToolResult`; `tool_failed` carries a safe error code, without the raw error payload.
Timeouts and tool-returned errors are failures. Calls refused by the tool budget emit
`tool_failed` with `skipped=True`, without a started event. Unexpected exceptions
still propagate after the failure event. Callback exceptions also propagate.

These events expose observable operations, not model reasoning. Tool arguments and
successful results can contain sensitive application data: the callback must select
what is suitable for display. Final results, ranking and conversation compaction are
unchanged; completed turns alone advance conversation memory.

## Semantic retrieval with memory

Use `SemanticRetrieval` for Chatbot-style retrieval: it reuses the existing pool,
deduplication, score decay and ranking. Its pool is separate from the agent's
conversation summary and survives compaction. Create one retrieval instance per
conversation and authorized collection/filter scope, just as for the agent.

```python
from ianuacare.core.retrieval import SemanticRetrieval

# Reuse the application's asynchronous query-embedding function.
# It accepts a string and returns list[float].
retrieval = SemanticRetrieval(
    reader, embed_query,
    collection=authorized_collection,
    filters=authorized_filters,  # Include the Reader's required `level` filter.
    rerank_top_k=8, score_decay=0.7, pool_max_size=50,
)
agent = Agent(llm, other_tools, retrieval=retrieval)
result = await agent.arun("Find relevant passages", request_context)
```

With `retrieval=...`, each turn starts with a semantic search before the first
model call. The model receives a paired tool call/result, including source IDs,
text and decayed scores. It can then call `search_context(query)` again to refine
the search or use any other tool. The automatic call shares the normal tool timeout
and call budget; validation failures and timeouts are visible to the model.

Set `auto_retrieve=False` to let the model decide when to search. Both modes use
the same component. Multiple searches within one turn do not age scores; turns
without a search still count towards decay. Rediscovered points refresh their
text, score and turn. Each successful search updates and bounds the pool, even
if the subsequent model answer fails; failed/cancelled searches do not update it.
The application may persist `retrieval.state.retrieved_pool` alongside the agent's
memory and turn index. Do not change the authorized scope while retaining a pool.

For custom orchestration, call `retrieval.search(query, context, turn=turn_index)`
or register `retrieval.as_tool(lambda: memory.turn_index)`. Database and PubMed
results are not added to this vector pool. This is the existing score/decay ranking,
not an additional reranker model.

Defaults are 8 model steps, 20 tool calls and 30 seconds per tool. `finish_reason`
is `completed`, `step_limit`, `tool_limit`, or `incomplete` (truncated/filtered model
output). Only completed turns update memory. Cancellation propagates. A failed run
does not roll back side effects of tools that already ran.

After a completed turn exceeds `max_context_chars` (default 4000), the agent asks
the LLM to summarize the entire conversation, including tool results, and retains
the system messages. It never removes half of a tool-call/result pair. This is a
compaction threshold, **not a hard token limit during a turn**: handlers should
return bounded results and expose pagination/selection where needed. Summarization
is a separate model call, outside the tool-loop step budget. `result.messages`
contains the completed transcript before compaction.

`LLMModel.achat` preserves `content`, `tool_calls` and `finish_reason`, bypassing
summary normalization. Together supports this contract. A custom `AIProvider`
must set `supports_tools = True`, accept tool definitions in `params`, and return
these keys from inference. Existing `run/arun` behavior is unchanged.

## PubMed over MCP

Start the existing PubMed server with Streamable HTTP. This complete example uses
`PUBMED_MCP_URL`, `TOGETHER_API_KEY`, and `TOGETHER_MODEL` from the environment:

```python
import asyncio
import os

from mcp import Client
from ianuacare import LLMModel, ModelOutNormalizer, RequestContext, TogetherAIProvider, User
from ianuacare.core.agent import Agent
from ianuacare.infrastructure.mcp import mcp_tools

async def main():
    model = os.environ["TOGETHER_MODEL"]  # Choose a model supporting tool calling.
    llm = LLMModel(
        TogetherAIProvider(os.environ["TOGETHER_API_KEY"], model),
        model, ModelOutNormalizer(),
    )
    async with mcp_tools(
        Client(os.environ["PUBMED_MCP_URL"]), namespace="pubmed",
        allow={"pubmed_search_articles", "pubmed_fetch_articles"},
    ) as tools:
        agent = Agent(llm, tools, system_prompt=(
            "Search PubMed, then fetch the articles before answering. Cite PMIDs. "
            "Send only bibliographic queries, never names, identifiers or clinical case data."
        ))
        context = RequestContext(User("demo", "reader", []), "example")
        result = await agent.arun("Find reviews on cognitive behavioral therapy", context)
        print(result.finish_reason, result.text)

asyncio.run(main())
```

For stdio replace the `Client` above with:

```python
from mcp import StdioServerParameters

Client(StdioServerParameters(
    command=os.environ["PUBMED_PYTHON"],  # Interpreter where PubMed is installed.
    args=["-m", "ianua_pubmed_mcp", "--transport", "stdio"],
))
```

`mcp_tools` owns the client's connection within its async context. Tool names are
qualified as `namespace__name`. Discovery follows pagination and rejects missing
allowlisted tools. Structured content, errors and source names are preserved;
other content blocks are serialized as JSON. Configure remote authentication on
the SDK client/transport. The local `RequestContext` is never forwarded to MCP.

## Generic data MCP server

The following runnable stdio server uses only fake in-memory records. Replace the
reader and resolver when integrating an application; no domain types are required.

```python
import asyncio

from mcp.server.stdio import stdio_server
from ianuacare.core.models import RequestContext, User
from ianuacare.core.tools import Tool
from ianuacare.infrastructure.mcp import create_structured_data_server

records = {"demo": {"example": {"value": 42}}}

async def resolve_context(mcp_context):
    # Demo only: a real resolver authenticates the caller and binds its scope.
    return RequestContext(User("demo", "reader", []), "example", {"scope": "demo"})

async def read_record(arguments, context):
    return {"record": records[context.metadata["scope"]].get(arguments["key"]),
            "source": arguments["key"]}

server = create_structured_data_server([
    Tool("read_record", "Read a record by key", {
        "type": "object", "properties": {"key": {"type": "string"}},
        "required": ["key"], "additionalProperties": False,
    }, read_record, read_only=True),
], resolve_context)

async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())

asyncio.run(main())
```

For HTTP serve `server.streamable_http_app()` with an ASGI server. Configure
authentication and the request context resolver before exposing real data. The
resolver runs on every call; absent or denied context prevents repository access.
Only tools explicitly declared `read_only=True` are accepted; the application is
responsible for that declaration matching the handler. Repository exceptions are
masked in protocol responses. The library does not implement database queries,
record authorization rules, or application audit persistence.
