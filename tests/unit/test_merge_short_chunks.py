"""Tests for merge_short_chunks (CAM++ segment-length adaptation)."""

from __future__ import annotations

from ianuacare.ai.parsers.segment_duration import (
    DEFAULT_MIN_EMBEDDING_SECONDS,
    merge_short_chunks,
)


def _dur(chunk: dict) -> float:
    return chunk["end"] - chunk["start"]


def test_empty_and_single_pass_through() -> None:
    assert merge_short_chunks([]) == []
    single = [{"start": 0.0, "end": 0.2, "text": "hi"}]
    assert merge_short_chunks(single) == single  # nothing to merge with


def test_merges_adjacent_short_chunks_up_to_min() -> None:
    chunks = [
        {"start": 0.0, "end": 0.4, "text": "a"},
        {"start": 0.4, "end": 0.8, "text": "b"},
        {"start": 0.8, "end": 1.2, "text": "c"},
        {"start": 1.2, "end": 2.5, "text": "d"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0)
    # First three (0.4s each) coalesce until >= 1.0s, then the long one stands.
    assert all(_dur(c) >= 1.0 for c in out)
    assert out[0]["start"] == 0.0
    assert out[-1]["end"] == 2.5
    assert "a b c" in out[0]["text"]


def test_trailing_short_chunk_merged_into_previous() -> None:
    chunks = [
        {"start": 0.0, "end": 1.5, "text": "long"},
        {"start": 1.5, "end": 1.7, "text": "tail"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0)
    assert len(out) == 1
    assert out[0]["end"] == 1.7
    assert out[0]["text"] == "long tail"


def test_total_shorter_than_min_returns_single_chunk() -> None:
    chunks = [
        {"start": 0.0, "end": 0.3, "text": "x"},
        {"start": 0.3, "end": 0.6, "text": "y"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0)
    assert len(out) == 1
    assert out[0]["start"] == 0.0 and out[0]["end"] == 0.6


def test_min_zero_is_noop_copy() -> None:
    chunks = [{"start": 0.0, "end": 0.1, "text": "a"}, {"start": 0.1, "end": 0.2, "text": "b"}]
    out = merge_short_chunks(chunks, min_seconds=0.0)
    assert out == chunks and out is not chunks


def test_default_min_is_one_second() -> None:
    assert DEFAULT_MIN_EMBEDDING_SECONDS == 1.0


def test_gap_break_prevents_merge_across_pause() -> None:
    """ianua-library#16: a pause > max_gap_seconds marks a speaker turn."""
    chunks = [
        {"start": 0.0, "end": 0.5, "text": "ciao"},
        {"start": 0.6, "end": 0.9, "text": "anna"},
        # 0.78s pause: likely turn change — never absorb across it
        {"start": 1.68, "end": 2.4, "text": "ciao"},
        {"start": 2.4, "end": 3.1, "text": "francesca"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0, max_gap_seconds=0.5)
    assert len(out) == 2
    assert out[0]["text"] == "ciao anna"
    assert out[1]["text"] == "ciao francesca"
    # first window stays < min_seconds rather than straddling the pause
    assert _dur(out[0]) < 1.0


def test_gap_break_none_keeps_legacy_behavior() -> None:
    chunks = [
        {"start": 0.0, "end": 0.5, "text": "a"},
        {"start": 1.5, "end": 2.0, "text": "b"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0, max_gap_seconds=None)
    assert len(out) == 1
    assert out[0]["text"] == "a b"


def test_trailing_short_chunk_not_absorbed_across_gap() -> None:
    chunks = [
        {"start": 0.0, "end": 1.5, "text": "long"},
        {"start": 2.5, "end": 2.9, "text": "tail"},
    ]
    out = merge_short_chunks(chunks, min_seconds=1.0, max_gap_seconds=0.5)
    assert len(out) == 2
    assert out[1]["text"] == "tail"
