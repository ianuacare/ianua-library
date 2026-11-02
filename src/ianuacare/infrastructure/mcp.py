"""Optional MCP adapter and generic read-only data server (``ianuacare[mcp]``)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from mcp import Client
from mcp import types as mt
from mcp.server import Server, ServerRequestContext

from ianuacare.core.exceptions import AuthorizationError, ValidationError
from ianuacare.core.models import RequestContext
from ianuacare.core.tools import Tool, ToolResult, tool_registry


@asynccontextmanager
async def mcp_tools(
    client: Client,
    *,
    namespace: str,
    allow: set[str] | None = None,
) -> AsyncIterator[list[Tool]]:
    """Connect, discover tools and close in the same async task.

    Configure URL/auth or stdio on the SDK Client. RequestContext is deliberately
    not sent to remote servers: their own authenticated context resolver applies.
    """
    async with client:
        tools: list[Tool] = []
        cursor: str | None = None
        while True:
            page = await client.list_tools(cursor=cursor)
            for remote in page.tools:
                if allow is not None and remote.name not in allow:
                    continue
                tools.append(_remote_tool(client, remote, namespace))
            cursor = page.next_cursor
            if cursor is None:
                break
        if allow is not None:
            discovered = {tool.name.removeprefix(f"{namespace}__") for tool in tools}
            if missing := allow - discovered:
                raise ValueError(f"MCP tools not found: {sorted(missing)}")
        yield tools


def _remote_tool(client: Client, remote: mt.Tool, namespace: str) -> Tool:
    async def call(arguments: dict[str, Any], context: RequestContext) -> ToolResult:
        result = await client.call_tool(remote.name, arguments)
        data: Any = result.structured_content
        if data is None:
            data = [block.model_dump(mode="json", by_alias=True) for block in result.content]
        return ToolResult(data, is_error=result.is_error, source=f"{namespace}/{remote.name}")

    return Tool(
        name=f"{namespace}__{remote.name}",
        description=remote.description or remote.name,
        input_schema=remote.input_schema,
        handler=call,
        read_only=bool(remote.annotations and remote.annotations.read_only_hint),
    )


def create_structured_data_server(
    tools: Iterable[Tool],
    context_resolver: Callable[[ServerRequestContext[Any]], Awaitable[RequestContext]],
    *,
    name: str = "ianua-structured-data",
) -> Server[Any]:
    """Expose application-supplied readers, without database or domain knowledge.

    The resolver must authenticate and bind an authorized scope on every call.
    Handlers enforce access to records within that scope. Never derive identity
    from tool arguments. The returned SDK Server supports stdio and HTTP.
    """
    registry = tool_registry(tools)
    if any(not tool.read_only for tool in registry.values()):
        raise ValueError("The structured data server accepts only read-only tools")

    async def list_tools(
        ctx: ServerRequestContext[Any],
        params: mt.PaginatedRequestParams | None,
    ) -> mt.ListToolsResult:
        return mt.ListToolsResult(
            tools=[
                mt.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    annotations=mt.ToolAnnotations(
                        read_only_hint=True,
                        destructive_hint=False,
                        open_world_hint=False,
                    ),
                )
                for tool in registry.values()
            ]
        )

    async def call_tool(
        ctx: ServerRequestContext[Any],
        params: mt.CallToolRequestParams,
    ) -> mt.CallToolResult:
        try:
            context = await context_resolver(ctx)
            if not isinstance(context, RequestContext):
                raise AuthorizationError("Missing authorized request context")
            tool = registry.get(params.name)
            if tool is None:
                raise ValidationError("Unknown tool")
            result = await tool.call(params.arguments or {}, context)
        except AuthorizationError:
            result = ToolResult("Access denied", is_error=True)
        except ValidationError as exc:
            result = ToolResult(exc.message, is_error=True)
        except Exception:
            # Database/transport exception text can contain credentials or record data.
            result = ToolResult("Tool execution failed", is_error=True)
        content = asdict(result)
        return mt.CallToolResult(
            content=[mt.TextContent(type="text", text=json.dumps(content, ensure_ascii=False))],
            structured_content=content,
            is_error=result.is_error,
        )

    return Server(
        name,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        get_tool_input_schema=lambda name: (
            registry[name].input_schema if name in registry else None
        ),
    )
