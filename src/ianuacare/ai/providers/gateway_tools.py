"""Stateless translation between the agent contract and native Converse blocks."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ianuacare.core.exceptions import InferenceError

_STATE_KEY = "inference_gateway_converse"


def _function(call: Any) -> dict[str, Any]:
    if not isinstance(call, dict) or call.get("type") != "function":
        raise ValueError("Only function tools are supported")
    function = call.get("function")
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        raise ValueError("A tool requires a function name")
    return function


def tool_config(tools: Any, choice: Any = "auto") -> dict[str, Any]:
    if not isinstance(tools, list) or not tools:
        raise ValueError("tools must be a non-empty list")
    converted = []
    for tool in tools:
        function = _function(tool)
        if set(tool) - {"type", "function"} or set(function) - {
            "name",
            "description",
            "parameters",
            "strict",
        }:
            raise ValueError("Unsupported tool definition fields")
        if function.get("strict"):
            raise ValueError("Strict tool schemas are not implemented by this gateway adapter")
        schema = function.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(schema, dict):
            raise ValueError("Tool parameters must be a JSON schema object")
        spec = {"name": function["name"], "inputSchema": {"json": deepcopy(schema)}}
        if function.get("description"):
            spec["description"] = function["description"]
        converted.append({"toolSpec": spec})
    selection: dict[str, Any]
    if choice == "auto":
        selection = {"auto": {}}
    elif choice == "required":
        selection = {"any": {}}
    elif isinstance(choice, dict):
        name = _function(choice)["name"]
        if name not in {item["toolSpec"]["name"] for item in converted}:
            raise ValueError("tool_choice must refer to a provided tool")
        selection = {"tool": {"name": name}}
    else:
        raise ValueError("Unsupported tool_choice; use auto, required or a named function")
    return {"tools": converted, "toolChoice": selection}


def _tool_use(call: Any) -> dict[str, Any]:
    function = _function(call)
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("A tool call requires an ID")
    try:
        arguments = json.loads(function.get("arguments", "{}"))
    except (ValueError, TypeError):
        raise ValueError("Tool arguments must be a JSON object") from None
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return {"toolUse": {"toolUseId": call_id, "name": function["name"], "input": arguments}}


def _visible(native: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    blocks = native.get("content")
    if native.get("role") != "assistant" or not isinstance(blocks, list):
        raise InferenceError("Invalid gateway assistant message")
    text, calls = [], []
    for block in blocks:
        if "text" in block:
            text.append(block["text"])
        if "toolUse" in block:
            use = block["toolUse"]
            if (
                not isinstance(use.get("toolUseId"), str)
                or not isinstance(use.get("name"), str)
                or not isinstance(use.get("input"), dict)
            ):
                raise InferenceError("Invalid gateway tool call")
            calls.append(
                {
                    "id": use["toolUseId"],
                    "type": "function",
                    "function": {
                        "name": use["name"],
                        "arguments": json.dumps(
                            use["input"], ensure_ascii=False, allow_nan=False, sort_keys=True
                        ),
                    },
                }
            )
    return "\n".join(text), calls


def messages_to_converse(messages: Any, model_name: str) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        raise ValueError("Chat messages must be a list")
    result: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Chat messages must be objects")
        role, content = message.get("role"), message.get("content")
        if set(message) - {"role", "content", "tool_calls", "tool_call_id", "provider_metadata"}:
            raise ValueError("Unsupported chat message fields")
        metadata = message.get("provider_metadata") or {}
        if metadata:
            state = metadata.get(_STATE_KEY)
            if (
                not isinstance(state, dict)
                or state.get("model") != model_name
                or role != "assistant"
            ):
                raise ValueError(
                    "Provider history belongs to a different model; start a new history"
                )
            native = state["message"]
            expected_text, expected_calls = _visible(native)
            if (content or "") != expected_text or (
                message.get("tool_calls") or []
            ) != expected_calls:
                raise ValueError(
                    "Assistant history was edited; cannot reuse signed provider blocks"
                )
            result.append(deepcopy(native))
            continue
        if role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id or not isinstance(content, str):
                raise ValueError("A tool result requires a call ID and text content")
            # Consecutive results from parallel calls are one user turn in Converse.
            block = {"toolResult": {"toolUseId": call_id, "content": [{"text": content}]}}
            try:
                value = json.loads(content)
            except ValueError:
                value = None
            if isinstance(value, dict) and value.get("is_error") is True:
                block["toolResult"]["status"] = "error"
            if (
                result
                and result[-1]["role"] == "user"
                and all("toolResult" in item for item in result[-1]["content"])
            ):
                result[-1]["content"].append(block)
            else:
                result.append({"role": "user", "content": [block]})
        elif role in {"system", "user", "assistant"}:
            if isinstance(content, list):
                if message.get("tool_calls"):
                    raise ValueError("Do not mix native content blocks with OpenAI tool_calls")
                blocks = deepcopy(content)
            elif isinstance(content, str) or content is None:
                blocks = [{"text": content}] if content else []
                if message.get("tool_calls"):
                    if role != "assistant":
                        raise ValueError("Only assistant messages can contain tool calls")
                    blocks.extend(_tool_use(call) for call in message["tool_calls"])
            else:
                raise ValueError("Unsupported message content")
            if not blocks:
                raise ValueError("Chat messages must not be empty")
            result.append({"role": role, "content": blocks})
        else:
            raise ValueError("Unsupported chat message role")
    return result


def response_to_agent(response: dict[str, Any], model_name: str) -> dict[str, Any]:
    native = response.get("message")
    if not isinstance(native, dict):
        raise InferenceError("Tool-enabled gateway model must return a native assistant message")
    text, calls = _visible(native)
    reasons = {
        "tool_use": "tool_calls",
        "max_tokens": "length",
        "model_context_window_exceeded": "length",
        "content_filtered": "content_filter",
        "guardrail_intervened": "content_filter",
        "end_turn": "stop",
        "stop_sequence": "stop",
    }
    reason = response.get("stop_reason")
    return {
        **response,
        "content": text,
        "text": text,
        "tool_calls": calls,
        "finish_reason": reasons.get(reason, reason) if isinstance(reason, str) else None,
        "provider_metadata": {_STATE_KEY: {"model": model_name, "message": deepcopy(native)}},
    }
