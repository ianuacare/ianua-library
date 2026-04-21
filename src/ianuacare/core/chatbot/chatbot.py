"""RAG-backed chat orchestration with cross-turn retrieval reranking."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from ianuacare.ai.models.inference.LLM import LLMModel
from ianuacare.core.chatbot.message import Message, RetrievedPoint
from ianuacare.core.exceptions.errors import ValidationError
from ianuacare.core.models.context import RequestContext
from ianuacare.infrastructure.storage.reader import Reader
from ianuacare.infrastructure.storage.writer import Writer


def _retry(
    operation: Callable[[], Any],
    *,
    max_retries: int,
    retry_base_delay: float,
) -> Any:
    """Retry with exponential backoff; validation errors propagate immediately."""
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except ValidationError:
            raise
        except BaseException as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            delay = retry_base_delay * (2**attempt)
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("_retry: unreachable")


async def _aretry_awaitable(
    factory: Callable[[], Awaitable[Any]],
    *,
    max_retries: int,
    retry_base_delay: float,
) -> Any:
    """Retry an async factory with exponential backoff."""
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return await factory()
        except ValidationError:
            raise
        except BaseException as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            delay = retry_base_delay * (2**attempt)
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("_aretry_awaitable: unreachable")


class ConversationState:
    """Mutable session state: messages, rolling summary, and pooled vector hits."""

    __slots__ = ("context", "summary", "retrieved_pool", "turn_index")

    def __init__(self, *, system_prompt: str | None = None) -> None:
        self.summary: str = ""
        self.retrieved_pool: list[RetrievedPoint] = []
        self.turn_index: int = 0
        self.context: list[Message] = []
        if system_prompt:
            self.context.append(Message(role="system", content=system_prompt))

    def total_chars(self) -> int:
        return sum(len(m.content) for m in self.context)

    def append_turn(self, user_content: str, assistant_content: str) -> None:
        self.context.append(Message(role="user", content=user_content))
        self.context.append(Message(role="assistant", content=assistant_content))
        self.turn_index += 1

    @staticmethod
    def _effective_score(point: RetrievedPoint, current_turn: int, score_decay: float) -> float:
        return float(point.score) * (score_decay ** (current_turn - point.turn))

    def merge_and_rerank(
        self,
        new_hits: list[dict[str, Any]],
        *,
        current_turn: int,
        rerank_top_k: int,
        score_decay: float,
    ) -> list[RetrievedPoint]:
        """Combine fresh vector hits with the pooled history and rank by relevance + decay."""
        new_points = [RetrievedPoint.from_vector_hit(h, current_turn) for h in new_hits]
        new_ids = {p.id for p in new_points}
        candidates: list[RetrievedPoint] = list(new_points)
        for old in self.retrieved_pool:
            if old.id not in new_ids:
                candidates.append(old)
        candidates.sort(
            key=lambda p: self._effective_score(p, current_turn, score_decay),
            reverse=True,
        )
        return candidates[:rerank_top_k]

    def prune_pool(
        self,
        *,
        reference_turn: int,
        score_decay: float,
        pool_max_size: int,
    ) -> None:
        """Keep only the top ``pool_max_size`` points by decayed score."""
        if pool_max_size <= 0:
            self.retrieved_pool = []
            return
        ranked = sorted(
            self.retrieved_pool,
            key=lambda p: self._effective_score(p, reference_turn, score_decay),
            reverse=True,
        )
        self.retrieved_pool = ranked[:pool_max_size]


class Chatbot:
    """Orchestrates retrieval, LLM calls, streaming, retries, and conversation state."""

    def __init__(
        self,
        reader: Reader,
        writer: Writer,
        llm: LLMModel,
        *,
        collection: str,
        filters: dict[str, Any],
        top_k: int = 10,
        score_threshold: float | None = None,
        rerank_top_k: int = 8,
        score_decay: float = 0.7,
        pool_max_size: int = 50,
        max_context_chars: int = 4000,
        system_prompt: str | None = None,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._llm = llm
        self._collection = collection
        self._filters = filters
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._rerank_top_k = rerank_top_k
        self._score_decay = score_decay
        self._pool_max_size = pool_max_size
        self._max_context_chars = max_context_chars
        self._system_prompt = system_prompt
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self.state = ConversationState(system_prompt=system_prompt)

    def _read_vector_search(self, query_vector: list[float], context_request: RequestContext) -> list[dict[str, Any]]:
        return self._reader.read_vector_search(
            self._collection,
            vector=query_vector,
            top_k=self._top_k,
            filters=dict(self._filters),
            score_threshold=self._score_threshold,
            context=context_request,
        )

    def inference(self, query: str, query_vector: list[float], context_request: RequestContext) -> str:
        """Run a synchronous chat turn."""
        current_turn = self.state.turn_index
        new_hits = _retry(
            lambda: self._read_vector_search(query_vector, context_request),
            max_retries=self._max_retries,
            retry_base_delay=self._retry_base_delay,
        )
        selected = self.state.merge_and_rerank(
            new_hits,
            current_turn=current_turn,
            rerank_top_k=self._rerank_top_k,
            score_decay=self._score_decay,
        )
        payload = self._build_llm_payload(query, selected)
        result = _retry(
            lambda: self._llm.run(payload),
            max_retries=self._max_retries,
            retry_base_delay=self._retry_base_delay,
        )
        msg_text = str(result.get("text") or "").strip()
        self._finalize_success(query, msg_text, new_hits, context_request)
        return msg_text

    async def ainference(self, query: str, query_vector: list[float], context_request: RequestContext) -> str:
        """Run an asynchronous chat turn."""
        current_turn = self.state.turn_index

        def _read_sync() -> list[dict[str, Any]]:
            return _retry(
                lambda: self._read_vector_search(query_vector, context_request),
                max_retries=self._max_retries,
                retry_base_delay=self._retry_base_delay,
            )

        new_hits = await asyncio.to_thread(_read_sync)
        selected = self.state.merge_and_rerank(
            new_hits,
            current_turn=current_turn,
            rerank_top_k=self._rerank_top_k,
            score_decay=self._score_decay,
        )
        payload = self._build_llm_payload(query, selected)
        result = await _aretry_awaitable(
            lambda: self._llm.arun(payload),
            max_retries=self._max_retries,
            retry_base_delay=self._retry_base_delay,
        )
        msg_text = str(result.get("text") or "").strip()
        self._finalize_success(query, msg_text, new_hits, context_request)
        return msg_text

    async def astream(
        self,
        query: str,
        query_vector: list[float],
        context_request: RequestContext,
    ) -> AsyncIterator[str]:
        """Stream assistant tokens; updates state after the full reply is assembled."""
        current_turn = self.state.turn_index

        def _read_sync() -> list[dict[str, Any]]:
            return _retry(
                lambda: self._read_vector_search(query_vector, context_request),
                max_retries=self._max_retries,
                retry_base_delay=self._retry_base_delay,
            )

        new_hits = await asyncio.to_thread(_read_sync)
        selected = self.state.merge_and_rerank(
            new_hits,
            current_turn=current_turn,
            rerank_top_k=self._rerank_top_k,
            score_decay=self._score_decay,
        )
        payload = self._build_llm_payload(query, selected)
        chunks: list[str] = []
        async for chunk in self._llm.astream(payload):
            chunks.append(chunk)
            yield chunk
        assembled = "".join(chunks).strip()
        normalized = self._llm.finalize_stream_text(assembled)
        msg_text = str(normalized.get("text") or assembled).strip()
        self._finalize_success(query, msg_text, new_hits, context_request)

    def _build_llm_payload(self, query: str, selected: list[RetrievedPoint]) -> dict[str, Any]:
        return {
            "summary": self.state.summary,
            "history": [{"role": m.role, "content": m.content} for m in self.state.context],
            "retrieved": [p.source_text for p in selected],
            "query": query,
        }

    def _merge_new_hits_into_pool(self, new_hits_raw: list[dict[str, Any]], turn: int) -> None:
        new_points = [RetrievedPoint.from_vector_hit(h, turn) for h in new_hits_raw]
        by_id: dict[str, RetrievedPoint] = {p.id: p for p in self.state.retrieved_pool}
        for p in new_points:
            by_id[p.id] = p
        self.state.retrieved_pool = list(by_id.values())

    def _maybe_summarize(self) -> None:
        if self.state.total_chars() <= self._max_context_chars:
            return
        summary_payload: dict[str, Any] = {
            "task": "summarize",
            "previous_summary": self.state.summary,
            "history": [{"role": m.role, "content": m.content} for m in self.state.context],
        }
        out = _retry(
            lambda: self._llm.run(summary_payload),
            max_retries=self._max_retries,
            retry_base_delay=self._retry_base_delay,
        )
        self.state.summary = str(out.get("text") or "").strip()
        self.state.context = []
        if self._system_prompt:
            self.state.context.append(Message(role="system", content=self._system_prompt))

    def _finalize_success(
        self,
        query: str,
        msg_text: str,
        new_hits_raw: list[dict[str, Any]],
        context_request: RequestContext,
    ) -> None:
        """Apply state updates only after a successful model response."""
        turn_for_hits = self.state.turn_index
        self._merge_new_hits_into_pool(new_hits_raw, turn_for_hits)
        self.state.append_turn(query, msg_text)
        self.state.prune_pool(
            reference_turn=self.state.turn_index,
            score_decay=self._score_decay,
            pool_max_size=self._pool_max_size,
        )
        self._maybe_summarize()
        log_line = json.dumps(
            {
                "event": "chatbot_turn",
                "turn": self.state.turn_index,
                "messages": [
                    {"role": "user", "content_len": len(query)},
                    {"role": "assistant", "content_len": len(msg_text)},
                ],
            },
            ensure_ascii=False,
        )
        self._writer.write_log(log_line, context_request)
