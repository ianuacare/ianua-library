"""Token-aware text chunking for embedding pipelines."""

from __future__ import annotations

from typing import Any

from ianuacare.ai.text.splitter import split_sentences, split_words
from ianuacare.core.exceptions.errors import ValidationError

DEFAULT_MAX_TOKENS = 512


def count_tokens(text: str, tokenizer: Any | None = None) -> int:
    """Count tokens in ``text`` using an optional SentencePiece-like tokenizer.

    Falls back to unicode-aware word count when ``tokenizer`` is ``None``.
    """
    if tokenizer is None:
        return len(split_words(text))
    if callable(tokenizer) and not hasattr(tokenizer, "encode"):
        return int(tokenizer(text))
    encode = getattr(tokenizer, "encode", None) or getattr(tokenizer, "EncodeAsIds", None)
    if encode is None:
        raise ValidationError("tokenizer must be callable or expose encode/EncodeAsIds")
    return len(encode(text))


def chunk_text(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    tokenizer: Any | None = None,
) -> list[str]:
    """Split ``text`` into chunks of at most ``max_tokens`` tokens.

    Empty/whitespace-only input yields ``[]``. Text within the limit is
    returned as a single chunk preserving the exact original string.
    """
    if max_tokens < 1:
        raise ValidationError("max_tokens must be a positive integer")
    if not text.strip():
        return []
    if count_tokens(text, tokenizer) <= max_tokens:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in split_sentences(text) or [text]:
        sentence_tokens = count_tokens(sentence, tokenizer)
        if sentence_tokens > max_tokens:
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0
            chunks.extend(_chunk_words(sentence, max_tokens=max_tokens, tokenizer=tokenizer))
            continue
        if current and current_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += sentence_tokens
    if current:
        chunks.append(" ".join(current))
    return chunks


def _chunk_words(
    text: str,
    *,
    max_tokens: int,
    tokenizer: Any | None,
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for word in split_words(text):
        word_tokens = count_tokens(word, tokenizer)
        if current and current_tokens + word_tokens > max_tokens:
            chunks.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(word)
        current_tokens += word_tokens
    if current:
        chunks.append(" ".join(current))
    return chunks
