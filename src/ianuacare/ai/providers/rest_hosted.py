"""REST-hosted model provider with injectable request/response hooks."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from ianuacare.ai.providers.base import AIProvider
from ianuacare.core.exceptions.errors import InferenceError

PostResult = tuple[int, bytes, Mapping[str, str]]


@dataclass(frozen=True)
class RestRequest:
    """HTTP request specification produced by ``build_request``."""

    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    url: str | None = None
    method: str = "POST"


class BuildRequestFn(Protocol):
    """Build an HTTP request from ``model_name`` and provider ``payload``."""

    def __call__(self, model_name: str, payload: Any) -> RestRequest:
        ...


class ParseResponseFn(Protocol):
    """Parse HTTP response bytes into provider raw output."""

    def __call__(
        self,
        status_code: int,
        body: bytes,
        *,
        headers: Mapping[str, str],
    ) -> Any:
        ...


class PostFn(Protocol):
    """Execute an HTTP request; used for tests and custom transports."""

    def __call__(self, request: RestRequest, *, timeout_seconds: float) -> PostResult:
        ...


def _default_post(request: RestRequest, *, timeout_seconds: float) -> PostResult:
    if not request.url:
        raise InferenceError("REST request URL is required")
    data = request.body
    req = urllib.request.Request(
        request.url,
        data=data,
        headers=dict(request.headers),
        method=request.method.upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            status = int(getattr(resp, "status", 200))
            body = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return status, body, hdrs
    except urllib.error.HTTPError as exc:
        err_body = exc.read() if exc.fp is not None else b""
        hdrs = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return int(exc.code), err_body, hdrs
    except urllib.error.URLError as exc:
        raise InferenceError(f"REST request failed: {exc.reason}") from exc


def _default_parse_response(
    status_code: int,
    body: bytes,
    *,
    headers: Mapping[str, str],
) -> Any:
    _ = headers
    if status_code < 200 or status_code >= 300:
        raise InferenceError(f"REST endpoint returned status {status_code}")
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InferenceError("REST endpoint returned non-JSON body") from exc


class RestHostedModelProvider(AIProvider):
    """POST inference to a hosted REST endpoint via injectable hooks."""

    def __init__(
        self,
        endpoint_url: str,
        *,
        api_key: str | None = None,
        build_request: BuildRequestFn,
        parse_response: ParseResponseFn | None = None,
        post_fn: PostFn | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        if not endpoint_url.strip():
            raise ValueError("endpoint_url is required")
        self._endpoint_url = endpoint_url.strip()
        self._api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._build_request = build_request
        self._parse_response = parse_response or _default_parse_response
        self._post = post_fn or _default_post
        self._timeout_seconds = timeout_seconds

    def infer(
        self, model_name: str, payload: Any, *, model_type: str | None = None
    ) -> Any:
        _ = model_type
        if not isinstance(payload, dict):
            raise ValueError("REST hosted model payload must be a mapping")

        rest_request = self._build_request(model_name, payload)
        url = rest_request.url or self._endpoint_url
        headers = dict(rest_request.headers)
        if self._api_key and not any(k.lower() == "authorization" for k in headers):
            headers["Authorization"] = f"Bearer {self._api_key}"

        outbound = RestRequest(
            url=url,
            headers=headers,
            body=rest_request.body,
            method=rest_request.method,
        )
        status, body, response_headers = self._post(
            outbound, timeout_seconds=self._timeout_seconds
        )
        return self._parse_response(status, body, headers=response_headers)
