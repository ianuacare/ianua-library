"""Token-based text chunking."""

from __future__ import annotations

import pytest

from ianuacare.ai.text.chunker import chunk_text, count_tokens
from ianuacare.core.exceptions.errors import ValidationError


class TestCountTokens:
    def test_default_uses_word_count(self) -> None:
        assert count_tokens("alfa beta gamma") == 3

    def test_accepts_callable(self) -> None:
        assert count_tokens("alfa beta", lambda t: len(t.split())) == 2

    def test_accepts_sentencepiece_like(self) -> None:
        class FakeSP:
            def encode(self, text: str) -> list[int]:
                return [0] * len(text.split())

        assert count_tokens("alfa beta gamma", FakeSP()) == 3


class TestChunkText:
    def test_short_text_is_single_chunk(self) -> None:
        assert chunk_text("ciao mondo") == ["ciao mondo"]

    def test_empty_text_yields_no_chunks(self) -> None:
        assert chunk_text("   ") == []

    def test_splits_long_text(self) -> None:
        chunks = chunk_text("uno due tre quattro cinque sei.", max_tokens=3)
        assert len(chunks) > 1

    def test_rejects_non_positive_max_tokens(self) -> None:
        with pytest.raises(ValidationError):
            chunk_text("x", max_tokens=0)
