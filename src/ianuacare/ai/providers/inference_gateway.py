"""HTTP client for the Ianua inference gateway, independent of AWS SDKs."""

from __future__ import annotations

import asyncio
import json
import math
import re
import urllib.error
import urllib.request
from collections.abc import Collection
from typing import Any
from urllib.parse import urlsplit

from ianuacare.ai.providers.base import AIProvider
from ianuacare.ai.providers.gateway_tools import (
    messages_to_converse,
    response_to_agent,
    tool_config,
)
from ianuacare.ai.providers.rest_hosted import PostFn, PostResult, RestRequest
from ianuacare.core.exceptions.errors import InferenceError

_EMBEDDING_TYPES = {"embedding", "embeddings"}
_PENDING_STATES = {"queued", "pending", "submission_unknown"}


class GatewayJobPending(InferenceError):
    """Inference has no result yet. Persist ``job``; do not submit it again."""

    def __init__(self, job: dict[str, Any]) -> None:
        super().__init__(
            "Gateway job has no completed result; persist its reference and consult get_job",
            code="gateway_job_pending",
        )
        self.job = dict(job)
        self.job_id: str = job["job_id"]
        self.model_name: str = job["model"]
        self.status: str = job["status"]


class GatewayHTTPError(InferenceError):
    """HTTP failure with machine-readable status, without echoing upstream contents."""

    def __init__(self, status_code: int, *, code: str, retry_after: str | None = None) -> None:
        super().__init__(f"Inference gateway returned HTTP {status_code}", code=code)
        self.status_code = status_code
        self.retry_after = retry_after


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any
    ) -> None:
        return None


def _transport(request: RestRequest, *, timeout_seconds: float) -> PostResult:
    req = urllib.request.Request(
        request.url or "",
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout_seconds) as response:
            return int(response.status), response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read(), dict(exc.headers or {})
        finally:
            exc.close()


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        raise ValueError(f"{name} must contain only letters, digits, underscores or hyphens")
    return value


class InferenceGatewayProvider(AIProvider):
    """Use model aliases through one HTTP gateway, without AWS-specific clients.

    ``infer`` returns a completed result compatible with existing AI models.
    ``submit`` returns the full response envelope, including async job references.
    No polling, retries or background jobs are started implicitly. Transport errors
    during a POST can mean that the remote job was accepted; never blindly replay it.

    Streaming inherits the base class's single completed chunk fallback. The
    current gateway has no token stream. Tools require explicit per-alias opt-in.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 600.0,
        batch_size: int = 32,
        tool_models: Collection[str] = (),
        post_fn: PostFn | None = None,
    ) -> None:
        url = urlsplit(base_url.strip())
        if (
            url.scheme not in {"http", "https"}
            or not url.netloc
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "base_url must be an absolute HTTP(S) URL without credentials or query"
            )
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self._base_url = base_url.strip().rstrip("/")
        self._api_key = api_key.strip() if api_key else None
        self._timeout_seconds = timeout_seconds
        self._batch_size = batch_size
        if isinstance(tool_models, (str, bytes)):
            raise ValueError("tool_models must be a collection of model aliases")
        self._tool_models = frozenset(_identifier(alias, "tool model") for alias in tool_models)
        self.supports_tools = bool(self._tool_models)
        self._post = post_fn or _transport

    def supports_tools_for(self, model_name: str) -> bool:
        return model_name in self._tool_models

    def infer(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        prepared = self._payload(payload, model_type)
        if model_type in _EMBEDDING_TYPES or "texts" in prepared:
            texts = prepared["texts"]
            _identifier(model_name, "model_name")
            vectors: list[list[float]] = []
            for start in range(0, len(texts), self._batch_size):
                batch = texts[start : start + self._batch_size]
                envelope = self.submit(
                    model_name,
                    {**prepared, "texts": batch},
                    model_type=model_type,
                    params=params,
                )
                result = self._completed(envelope, model_type="embedding")
                if not isinstance(result, list) or len(result) != len(batch):
                    raise InferenceError("Gateway vector count does not match the input batch")
                if vectors and result and len(vectors[0]) != len(result[0]):
                    raise InferenceError("Gateway embedding dimension changed between batches")
                vectors.extend(result)
            return vectors
        result = self._completed(
            self.submit(model_name, prepared, model_type=model_type, params=params),
            model_type=model_type,
        )
        if self.supports_tools_for(model_name) and isinstance(result, dict):
            return response_to_agent(result, model_name)
        return result

    def submit(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit one request and return its envelope; never split async jobs.

        For embeddings, callers explicitly split into endpoint-sized batches when
        submitting jobs. A synchronous alias may return ``status=completed``.
        """
        _identifier(model_name, "model_name")
        if params is not None and not isinstance(params, dict):
            raise ValueError("params must be a mapping")
        prepared = self._payload(payload, model_type)
        request_params = dict(params or {})
        messages = prepared.get("messages", [])
        if not isinstance(messages, list):
            raise ValueError("messages must be a list")
        has_tool_history = any(
            isinstance(message, dict)
            and (
                message.get("role") == "tool"
                or message.get("tool_calls")
                or message.get("provider_metadata")
                or (
                    isinstance(message.get("content"), list)
                    and any(
                        isinstance(block, dict) and ("toolUse" in block or "toolResult" in block)
                        for block in message["content"]
                    )
                )
            )
            for message in messages
        )
        requests_tools = (
            "tools" in request_params
            or "tool_choice" in request_params
            or "tool_config" in prepared
            or has_tool_history
        )
        if requests_tools and (
            not self.supports_tools_for(model_name) or model_type in _EMBEDDING_TYPES
        ):
            raise ValueError("Tools are not enabled for this model alias")
        if self.supports_tools_for(model_name) and "messages" in prepared:
            if "tools" in request_params:
                if "tool_config" in prepared:
                    raise ValueError("Do not mix tools with native tool_config")
                prepared["tool_config"] = tool_config(
                    request_params.pop("tools"),
                    request_params.pop("tool_choice", "auto"),
                )
            elif "tool_choice" in request_params:
                raise ValueError("tool_choice requires tools")
            prepared["messages"] = messages_to_converse(messages, model_name)
        elif "tools" in request_params:
            raise ValueError("Tool requests require chat messages")
        body = {
            "model": model_name,
            "payload": prepared,
            "params": request_params,
        }
        result = self._request("POST", "/infer", body)
        self._validate_envelope(result, model_name)
        return result

    def get_job(self, model_name: str, job_id: str) -> dict[str, Any]:
        """Read the job reference; never follow a server-supplied status_url."""
        _identifier(model_name, "model_name")
        _identifier(job_id, "job_id")
        result = self._request("GET", f"/jobs/{model_name}/{job_id}")
        self._validate_envelope(result, model_name)
        if result.get("job_id") != job_id:
            raise InferenceError("Gateway returned a different job ID")
        return result

    def get_result(
        self,
        model_name: str,
        job_id: str,
        *,
        model_type: str | None = None,
    ) -> Any:
        """Read and normalize a completed job, or raise GatewayJobPending."""
        return self._completed(self.get_job(model_name, job_id), model_type=model_type)

    async def asubmit(
        self,
        model_name: str,
        payload: Any,
        *,
        model_type: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.submit,
            model_name,
            payload,
            model_type=model_type,
            params=params,
        )

    async def aget_job(self, model_name: str, job_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self.get_job, model_name, job_id)

    async def aget_result(
        self, model_name: str, job_id: str, *, model_type: str | None = None
    ) -> Any:
        return await asyncio.to_thread(self.get_result, model_name, job_id, model_type=model_type)

    @staticmethod
    def _payload(payload: Any, model_type: str | None) -> dict[str, Any]:
        if model_type in _EMBEDDING_TYPES:
            if isinstance(payload, str):
                payload = {"texts": [payload]}
            elif isinstance(payload, list):
                payload = {"texts": payload}
        elif isinstance(payload, str):
            payload = {"messages": [{"role": "user", "content": payload}]}
        elif isinstance(payload, list):
            payload = {"messages": payload}
        if (
            isinstance(payload, dict)
            and model_type in {None, "chat", "llm", "text"}
            and "messages" not in payload
            and ("prompt" in payload or "text" in payload)
            and set(payload) <= {"prompt", "text", "context", "schema", "prompt_extras"}
        ):
            # InputDataParser has already assembled context/schema into prompt.
            text = payload.get("prompt") or payload.get("text")
            if not isinstance(text, str):
                raise ValueError("Chat prompt/text must be a string")
            payload = {"messages": [{"role": "user", "content": text}]}
        if not isinstance(payload, dict):
            raise ValueError("Gateway payload must be a mapping, chat text or message list")
        if model_type in _EMBEDDING_TYPES or "texts" in payload:
            texts = payload.get("texts")
            if not isinstance(texts, list) or not all(
                isinstance(text, str) and text.strip() for text in texts
            ):
                raise ValueError("Embedding payload requires a list of non-empty texts")
        return dict(payload)

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        encoded = json.dumps(body, allow_nan=False).encode("utf-8") if body is not None else None
        request = RestRequest(
            url=self._base_url + path,
            method=method,
            headers=headers,
            body=encoded,
        )
        try:
            status, raw, response_headers = self._post(
                request, timeout_seconds=self._timeout_seconds
            )
        except Exception:
            raise InferenceError(
                "Gateway transport failed; POST acceptance may be unknown; do not retry blindly",
                code="gateway_transport_error",
            ) from None
        if status not in {200, 202}:
            code = "gateway_http_error"
            try:
                candidate = json.loads(raw)["error"]["code"]
                if isinstance(candidate, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", candidate):
                    code = candidate
            except (ValueError, TypeError, KeyError):
                pass
            lowered = {key.lower(): value for key, value in response_headers.items()}
            raise GatewayHTTPError(status, code=code, retry_after=lowered.get("retry-after"))
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise InferenceError("Gateway returned invalid JSON") from None
        if not isinstance(data, dict):
            raise InferenceError("Gateway response must be an object")
        return data

    @staticmethod
    def _validate_envelope(data: dict[str, Any], model_name: str) -> None:
        if data.get("model") != model_name:
            raise InferenceError("Gateway response model does not match the requested alias")
        status = data.get("status")
        if not isinstance(status, str) or status not in _PENDING_STATES | {"completed", "failed"}:
            raise InferenceError("Gateway returned an unknown job status")
        if data["status"] in _PENDING_STATES:
            job_id = data.get("job_id")
            if not isinstance(job_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
                raise InferenceError("Gateway response is missing a valid job reference")

    @staticmethod
    def _completed(envelope: dict[str, Any], *, model_type: str | None) -> Any:
        status = envelope["status"]
        if status in _PENDING_STATES:
            raise GatewayJobPending(envelope)
        if status == "failed":
            raise InferenceError("Gateway inference job failed", code="gateway_job_failed")
        if "job_id" in envelope and "result" not in envelope:
            raise InferenceError("Completed gateway job is missing its result")
        result = envelope["result"] if "job_id" in envelope else envelope
        if not isinstance(result, dict):
            raise InferenceError("Gateway inference result must be an object")
        if model_type in _EMBEDDING_TYPES or "embeddings" in result:
            vectors = result.get("embeddings")
            if not isinstance(vectors, list):
                raise InferenceError("Gateway response is missing embeddings")
            dimension = len(vectors[0]) if vectors and isinstance(vectors[0], list) else 0
            for vector in vectors:
                if not isinstance(vector, list) or not vector or len(vector) != dimension:
                    raise InferenceError("Gateway embedding dimensions are inconsistent")
                for component in vector:
                    if isinstance(component, bool) or not isinstance(component, (int, float)):
                        raise InferenceError("Gateway embedding components must be finite numbers")
                    try:
                        finite = math.isfinite(component)
                    except OverflowError:
                        finite = False
                    if not finite:
                        raise InferenceError("Gateway embedding components must be finite numbers")
            return [[float(component) for component in vector] for vector in vectors]
        # Preserve complete Converse messages, signed reasoning blocks and usage;
        # do not pretend to support the OpenAI tool_calls interface of LLMModel.achat.
        return dict(result)
