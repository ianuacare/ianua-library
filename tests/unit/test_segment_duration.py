"""Tests for segment duration splitting and labeled chunk merging."""

from __future__ import annotations

from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.parsers.segment_duration import merge_labeled_chunks, split_by_max_duration


def test_pause_parser_skips_merge_when_disabled() -> None:
    parser = PauseParser(silence_gap_seconds=1.5, merge_gaps=False)
    out = parser.parse(
        [
            {"start": 0.0, "end": 1.0, "text": "a"},
            {"start": 1.2, "end": 2.0, "text": "b"},
        ]
    )
    assert len(out) == 2


def test_split_by_max_duration_creates_sub_chunks() -> None:
    chunks = split_by_max_duration(
        [{"start": 0.0, "end": 100.0, "text": "one two three four five six"}],
        max_duration_seconds=30.0,
    )
    assert len(chunks) == 4
    assert chunks[0]["start"] == 0.0
    assert chunks[-1]["end"] == 100.0
    assert " ".join(chunk["text"] for chunk in chunks if chunk["text"]).split() == [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
    ]


def test_merge_labeled_chunks_combines_same_speaker() -> None:
    chunks = [
        {"start": 0.0, "end": 10.0, "text": "hello"},
        {"start": 10.0, "end": 20.0, "text": "world"},
        {"start": 20.0, "end": 30.0, "text": "other"},
    ]
    merged = merge_labeled_chunks(chunks, [0, 0, 1])
    assert len(merged) == 2
    assert merged[0]["speaker_id"] == 0
    assert merged[0]["end"] == 20.0
    assert "hello" in merged[0]["text"]
    assert "world" in merged[0]["text"]


def test_merge_labeled_chunks_skips_merge_when_disabled() -> None:
    chunks = [
        {"start": 0.0, "end": 10.0, "text": "hello"},
        {"start": 10.0, "end": 20.0, "text": "world"},
        {"start": 20.0, "end": 30.0, "text": "other"},
    ]
    labeled = merge_labeled_chunks(chunks, [0, 0, 1], merge_consecutive=False)
    assert len(labeled) == 3
    assert labeled[0]["speaker_id"] == 0
    assert labeled[1]["speaker_id"] == 0
    assert labeled[2]["speaker_id"] == 1
