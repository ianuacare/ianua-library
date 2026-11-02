"""Semantic retrieval with a conversation-local pool, using Chatbot's ranking."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from ianuacare.core.chatbot.chatbot import ConversationState
from ianuacare.core.models import RequestContext
from ianuacare.core.tools import Tool, ToolResult
from ianuacare.infrastructure.storage.reader import Reader


class SemanticRetrieval:
    """One instance per conversation and authorized collection/filter scope.

    Embedding is injected to reuse the application's model and preprocessing.
    Successful searches update the pool independently of conversation compaction.
    ``turn`` is the conversation turn, not the number of searches performed.
    """

    def __init__(
        self,
        reader: Reader,
        embed: Callable[[str], Awaitable[list[float]]],
        *,
        collection: str,
        filters: dict[str, Any],
        top_k: int = 10,
        score_threshold: float | None = None,
        rerank_top_k: int = 8,
        score_decay: float = 0.7,
        pool_max_size: int = 50,
    ) -> None:
        self._reader = reader
        self._embed = embed
        self._collection = collection
        self._filters = dict(filters)
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._rerank_top_k = rerank_top_k
        self._score_decay = score_decay
        self._pool_max_size = pool_max_size
        self.state = ConversationState()

    async def search(self, query: str, context: RequestContext, *, turn: int) -> ToolResult:
        vector = await self._embed(query)
        hits = await asyncio.to_thread(
            self._reader.read_vector_search,
            self._collection,
            vector=vector,
            top_k=self._top_k,
            filters=dict(self._filters),
            score_threshold=self._score_threshold,
            context=context,
        )
        selected = self.state.merge_and_rerank(
            hits,
            current_turn=turn,
            rerank_top_k=self._rerank_top_k,
            score_decay=self._score_decay,
        )
        self.state.merge_hits(hits, turn)
        self.state.prune_pool(
            reference_turn=turn,
            score_decay=self._score_decay,
            pool_max_size=self._pool_max_size,
        )
        return ToolResult(
            [
                {**asdict(point), "score": point.score * self._score_decay ** (turn - point.turn)}
                for point in selected
            ],
            source=self._collection,
        )

    def as_tool(
        self,
        current_turn: Callable[[], int],
        *,
        name: str = "search_context",
    ) -> Tool:
        async def search(arguments: dict[str, Any], context: RequestContext) -> ToolResult:
            return await self.search(arguments["query"], context, turn=current_turn())

        return Tool(
            name=name,
            description=(
                "Search the authorized semantic collection. Returns relevant passages and "
                "source IDs, including still-relevant results from earlier conversation turns."
            ),
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=search,
            read_only=True,
        )
