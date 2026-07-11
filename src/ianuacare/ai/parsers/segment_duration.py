"""Split transcript segments for finer speaker embedding and diarization output.

Two splitting strategies are provided:

* :func:`split_by_max_duration` — time-uniform fallback (Phase 1 default).
* :func:`split_by_spectral_boundaries` — data-driven split at spectral
  change-points detected by :mod:`spectral_segmenter`.
"""

from __future__ import annotations

import math
from typing import Any

from ianuacare.ai._numeric import to_float

DEFAULT_MAX_SEGMENT_SECONDS = 30.0
_MIN_CHUNK_SECONDS = 0.05
_LABEL_GAP_TOLERANCE_SECONDS = 0.05

# Neural speaker embedders (e.g. CAM++) need enough speech per window to produce
# a stable embedding; below ~1s the vector is noisy and hurts clustering.
DEFAULT_MIN_EMBEDDING_SECONDS = 1.0

# A silence gap longer than this between adjacent chunks marks a likely speaker
# turn: embedding windows never merge across it (see merge_short_chunks).
DEFAULT_MERGE_MAX_GAP_SECONDS = 0.5


def merge_short_chunks(
    segments: list[dict[str, Any]],
    *,
    min_seconds: float = DEFAULT_MIN_EMBEDDING_SECONDS,
    max_gap_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Consolidate adjacent chunks so each spans at least ``min_seconds``.

    Applied before speaker embedding: a chunk shorter than ``min_seconds`` is
    absorbed into the following one (times extended, text concatenated). A
    trailing too-short chunk is merged back into the previous kept chunk. When
    the total audio is shorter than ``min_seconds`` a single chunk is returned.

    When ``max_gap_seconds`` is set, chunks separated by a silence gap larger
    than it are never merged: with word-level chunks an inter-word pause is
    strong evidence of a speaker turn, and a window straddling two speakers
    yields a mixed embedding that degrades clustering. Windows left shorter
    than ``min_seconds`` by such a break are kept as-is (the embedder decides
    whether they carry enough speech).

    The original list is not modified.
    """
    if min_seconds <= 0 or len(segments) <= 1:
        return [dict(segment) for segment in segments]

    def _duration(chunk: dict[str, Any]) -> float:
        return to_float(chunk.get("end"), 0.0) - to_float(chunk.get("start"), 0.0)

    def _absorb(target: dict[str, Any], other: dict[str, Any]) -> None:
        target["end"] = max(to_float(target.get("end"), 0.0), to_float(other.get("end"), 0.0))
        pieces = (str(target.get("text", "")).strip(), str(other.get("text", "")).strip())
        target["text"] = " ".join(piece for piece in pieces if piece).strip()

    def _gap_breaks(prev: dict[str, Any], nxt: dict[str, Any]) -> bool:
        if max_gap_seconds is None:
            return False
        gap = to_float(nxt.get("start"), 0.0) - to_float(prev.get("end"), 0.0)
        return gap > max_gap_seconds

    merged: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for segment in segments:
        candidate = {
            "start": to_float(segment.get("start"), 0.0),
            "end": to_float(segment.get("end"), to_float(segment.get("start"), 0.0)),
            "text": str(segment.get("text", "")).strip(),
        }
        if current is None:
            current = candidate
            continue
        if _gap_breaks(current, candidate):
            merged.append(current)
            current = candidate
            continue
        if _duration(current) < min_seconds:
            _absorb(current, candidate)
            continue
        merged.append(current)
        current = candidate

    if current is not None:
        if _duration(current) < min_seconds and merged and not _gap_breaks(merged[-1], current):
            _absorb(merged[-1], current)
        else:
            merged.append(current)
    return merged


def split_by_max_duration(
    segments: list[dict[str, Any]],
    *,
    max_duration_seconds: float = DEFAULT_MAX_SEGMENT_SECONDS,
) -> list[dict[str, Any]]:
    """Split segments longer than ``max_duration_seconds`` into time-aligned sub-chunks."""
    if max_duration_seconds <= 0:
        return [dict(segment) for segment in segments]

    chunks: list[dict[str, Any]] = []
    for segment in segments:
        start = to_float(segment.get("start"), 0.0)
        end = to_float(segment.get("end"), start)
        duration = max(0.0, end - start)
        text = str(segment.get("text", "")).strip()

        if duration <= max_duration_seconds or duration < _MIN_CHUNK_SECONDS:
            chunks.append({"start": start, "end": end, "text": text})
            continue

        n_parts = max(1, math.ceil(duration / max_duration_seconds))
        if duration / n_parts < _MIN_CHUNK_SECONDS:
            n_parts = max(1, math.ceil(duration / _MIN_CHUNK_SECONDS))

        part_duration = duration / n_parts
        for index in range(n_parts):
            part_start = start + index * part_duration
            part_end = start + (index + 1) * part_duration if index < n_parts - 1 else end
            frac_start = index / n_parts
            frac_end = (index + 1) / n_parts
            chunks.append(
                {
                    "start": part_start,
                    "end": part_end,
                    "text": _slice_text_by_fraction(text, frac_start, frac_end),
                }
            )
    return chunks


def merge_labeled_chunks(
    chunks: list[dict[str, Any]],
    labels: list[int],
    *,
    merge_consecutive: bool = True,
) -> list[dict[str, Any]]:
    """Attach speaker labels to chunks, optionally merging consecutive same-speaker runs."""
    if not chunks:
        return []

    aligned = _align_labels(labels, len(chunks))
    if not merge_consecutive:
        return [
            {
                "start": to_float(chunk.get("start"), 0.0),
                "end": to_float(chunk.get("end"), to_float(chunk.get("start"), 0.0)),
                "text": str(chunk.get("text", "")).strip(),
                "speaker_id": label,
            }
            for chunk, label in zip(chunks, aligned, strict=True)
        ]

    merged: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for chunk, label in zip(chunks, aligned, strict=True):
        start = to_float(chunk.get("start"), 0.0)
        end = to_float(chunk.get("end"), start)
        text = str(chunk.get("text", "")).strip()

        if current is None:
            current = {"start": start, "end": end, "text": text, "speaker_id": label}
            continue

        prev_end = to_float(current.get("end"), 0.0)
        same_speaker = int(current.get("speaker_id", 0)) == label
        contiguous = start <= prev_end + _LABEL_GAP_TOLERANCE_SECONDS

        if same_speaker and contiguous:
            current["end"] = max(prev_end, end)
            if text:
                prev_text = str(current.get("text", "")).strip()
                current["text"] = " ".join(piece for piece in (prev_text, text) if piece).strip()
            continue

        merged.append(current)
        current = {"start": start, "end": end, "text": text, "speaker_id": label}

    if current is not None:
        merged.append(current)
    return merged


def split_by_spectral_boundaries(
    segments: list[dict[str, Any]],
    boundaries: list[float],
    *,
    min_chunk_seconds: float = _MIN_CHUNK_SECONDS,
) -> list[dict[str, Any]]:
    """Split ASR segments at pre-computed spectral boundary timestamps.

    For each segment, every boundary that falls strictly inside its
    ``[start, end)`` interval creates a cut.  Text is distributed
    proportionally by word count, exactly as in :func:`split_by_max_duration`.

    Boundaries that fall outside all segments are silently ignored.

    Args:
        segments: List of dicts with ``start``, ``end``, and ``text`` keys.
        boundaries: Sorted list of boundary timestamps in seconds (as
            returned by :func:`spectral_segmenter.detect_spectral_boundaries`).
        min_chunk_seconds: Sub-chunks shorter than this are merged into the
            preceding chunk to avoid near-empty embedding windows.

    Returns:
        New list of segment dicts.  Each dict has ``start``, ``end``, and
        ``text``.  The original list is not modified.
    """
    sorted_boundaries = sorted(boundaries)
    chunks: list[dict[str, Any]] = []

    for segment in segments:
        start = to_float(segment.get("start"), 0.0)
        end = to_float(segment.get("end"), start)
        text = str(segment.get("text", "")).strip()
        duration = max(0.0, end - start)

        if duration < _MIN_CHUNK_SECONDS:
            chunks.append({"start": start, "end": end, "text": text})
            continue

        # Collect cut points inside this segment
        cuts = [t for t in sorted_boundaries if start < t < end]
        if not cuts:
            chunks.append({"start": start, "end": end, "text": text})
            continue

        # Build sub-intervals
        edges = [start, *cuts, end]
        sub_chunks: list[dict[str, Any]] = []
        for i in range(len(edges) - 1):
            sub_start = edges[i]
            sub_end = edges[i + 1]
            frac_start = (sub_start - start) / duration
            frac_end = (sub_end - start) / duration
            sub_chunks.append(
                {
                    "start": sub_start,
                    "end": sub_end,
                    "text": _slice_text_by_fraction(text, frac_start, frac_end),
                }
            )

        # Absorb sub-chunks that are too short into the next chunk.
        # We do a forward pass: if the *previous* kept chunk is below the
        # minimum, merge it into the current one.
        kept: list[dict[str, Any]] = []
        for sub in sub_chunks:
            if kept:
                prev = kept[-1]
                prev_dur = to_float(prev.get("end"), 0.0) - to_float(prev.get("start"), 0.0)
                if prev_dur < min_chunk_seconds:
                    # Absorb the too-short previous chunk into the current one
                    merged_text = " ".join(
                        p for p in (prev.get("text", ""), sub.get("text", "")) if p
                    ).strip()
                    kept[-1] = {
                        "start": prev["start"],
                        "end": sub["end"],
                        "text": merged_text,
                    }
                    continue
            kept.append(dict(sub))

        chunks.extend(kept)

    return chunks


def _slice_text_by_fraction(text: str, frac_start: float, frac_end: float) -> str:
    words = text.split()
    if not words:
        return ""
    n = len(words)
    start_index = min(n, max(0, int(frac_start * n)))
    end_index = min(n, max(start_index, int(frac_end * n)))
    if start_index >= end_index and end_index < n:
        end_index = start_index + 1
    return " ".join(words[start_index:end_index])


def _align_labels(labels: list[int], n: int) -> list[int]:
    if n <= 0:
        return []
    if len(labels) == n:
        return list(labels)
    if not labels:
        return [0] * n
    if len(labels) < n:
        pad = labels[-1]
        return [*labels, *([pad] * (n - len(labels)))]
    return list(labels[:n])
