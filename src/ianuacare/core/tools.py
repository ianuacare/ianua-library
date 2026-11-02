"""Small, shared contract for local functions and MCP tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from ianuacare.core.exceptions import ValidationError
from ianuacare.core.models import RequestContext


@dataclass
class ToolResult:
    data: Any
    is_error: bool = False
    source: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], RequestContext], Awaitable[Any]]
    read_only: bool = False

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    async def call(self, arguments: dict[str, Any], context: RequestContext) -> ToolResult:
        import jsonschema  # type: ignore[import-untyped]

        try:
            jsonschema.validate(arguments, self.input_schema)
        except jsonschema.ValidationError as exc:
            # Do not echo input values, which may contain sensitive data.
            raise ValidationError("Arguments do not match the tool input schema") from exc
        result = await self.handler(arguments, context)
        return result if isinstance(result, ToolResult) else ToolResult(result)


def tool_registry(tools: Iterable[Tool]) -> dict[str, Tool]:
    registry: dict[str, Tool] = {}
    for tool in tools:
        if tool.name in registry:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        registry[tool.name] = tool
    return registry
