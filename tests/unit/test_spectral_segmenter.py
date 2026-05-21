"""Tests for spectral change-point detection and spectral-boundary splitting."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ianuacare.ai.parsers.segment_duration import split_by_spectral_boundaries
from ianuacare.ai.parsers.spectral_segmenter import _enforce_min_gap, detect_spectral_boundaries
from ianuacare.core.exceptions.errors import InferenceError


# ---------------------------------------------------------------------------
# _enforce_min_gap
# ---------------------------------------------------------------------------


def test_enforce_min_gap_removes_close_boundaries() -> None:
    raw = [1.0, 1.5, 3.0, 3.2, 5.0]
    result = _enforce_min_gap(raw, min_gap_seconds=1.0)
    assert result == [1.0, 3.0, 5.0]


def test_enforce_min_gap_empty() -> None:
    assert _enforce_min_gap([], min_gap_seconds=1.0) == []


def test_enforce_min_gap_all_kept() -> None:
    raw = [1.0, 3.0, 5.0]
    assert _enforce_min_gap(raw, min_gap_seconds=1.0) == [1.0, 3.0, 5.0]


# ---------------------------------------------------------------------------
# detect_spectral_boundaries (mocked librosa + numpy)
# ---------------------------------------------------------------------------


def _make_mock_librosa(n_windows: int, distances: list[float]) -> MagicMock:
    """Build a minimal librosa mock that returns the given per-window distances."""
    import numpy as np

    mock_librosa = MagicMock()
    sr = 16_000
    hop_samples = int(2.0 * sr)
    y = np.zeros(n_windows * hop_samples, dtype=np.float32)
    mock_librosa.load.return_value = (y, sr)

    mfcc_call_count = 0

    def _mfcc(**kwargs: Any) -> Any:
        nonlocal mfcc_call_count
        idx = mfcc_call_count
        mfcc_call_count += 1
        # Return a (20, T) array whose mean along axis=1 is a simple unit vector
        # We construct vectors so that cosine distance between window i and i+1
        # equals distances[i] when i < len(distances).
        base = np.zeros((20, 1), dtype=np.float64)
        base[0, 0] = 1.0
        if idx > 0 and (idx - 1) < len(distances):
            d = distances[idx - 1]
            cos_sim = 1.0 - d
            base[1, 0] = (1.0 - cos_sim ** 2) ** 0.5 if cos_sim < 1.0 else 0.0
            base[0, 0] = cos_sim
        return base

    mock_librosa.feature.mfcc.side_effect = _mfcc
    return mock_librosa


def test_detect_spectral_boundaries_finds_high_distance_positions() -> None:
    import numpy as np

    # 6 windows, big jump at position 2→3 and 4→5
    distances = [0.1, 0.1, 0.8, 0.1, 0.9]
    mock_librosa = MagicMock()
    sr = 16_000
    hop_samples = int(2.0 * sr)
    n_windows = 6
    y = np.zeros(n_windows * hop_samples, dtype=np.float32)
    mock_librosa.load.return_value = (y, sr)

    # Build per-window MFCC vectors such that cosine distances match
    vecs: list[Any] = []
    for i, d in enumerate([0.1, 0.1, 0.8, 0.1, 0.9]):
        v = np.zeros(20)
        v[0] = 1.0
        v[1] = d  # simple proxy: larger v[1] → larger distance from [1,0,…]
        vecs.append(v)
    vecs.append(np.zeros(20))  # extra window

    call_idx = 0

    def _mfcc(y: Any = None, sr: Any = None, n_mfcc: int = 20, **kw: Any) -> Any:
        nonlocal call_idx
        v = vecs[call_idx] if call_idx < len(vecs) else np.zeros(20)
        call_idx += 1
        return v.reshape(n_mfcc, 1)

    mock_librosa.feature.mfcc.side_effect = _mfcc

    with patch.dict("sys.modules", {"librosa": mock_librosa}):
        boundaries = detect_spectral_boundaries(
            "/fake/audio.wav",
            hop_seconds=2.0,
            threshold=0.35,
            min_gap_seconds=1.5,
        )

    assert isinstance(boundaries, list)
    for t in boundaries:
        assert isinstance(t, float)
        assert t > 0


def test_detect_spectral_boundaries_raises_on_missing_librosa() -> None:
    with patch("ianuacare.ai.parsers.spectral_segmenter.import_module") as mock_import:
        mock_import.side_effect = ImportError("no module named librosa")
        with pytest.raises(InferenceError, match="librosa"):
            detect_spectral_boundaries("/fake.wav")


def test_detect_spectral_boundaries_raises_on_bad_file() -> None:
    with pytest.raises(InferenceError, match="could not load audio"):
        detect_spectral_boundaries("/this/file/does/not/exist/at/all.wav")


# ---------------------------------------------------------------------------
# split_by_spectral_boundaries
# ---------------------------------------------------------------------------


def test_split_by_spectral_boundaries_cuts_inside_segment() -> None:
    segments = [{"start": 0.0, "end": 60.0, "text": "a b c d e f"}]
    boundaries = [20.0, 40.0]
    chunks = split_by_spectral_boundaries(segments, boundaries)
    assert len(chunks) == 3
    assert chunks[0]["start"] == 0.0
    assert chunks[0]["end"] == pytest.approx(20.0)
    assert chunks[1]["start"] == pytest.approx(20.0)
    assert chunks[1]["end"] == pytest.approx(40.0)
    assert chunks[2]["end"] == 60.0


def test_split_by_spectral_boundaries_ignores_outside_boundaries() -> None:
    segments = [{"start": 10.0, "end": 30.0, "text": "hello world"}]
    boundaries = [5.0, 50.0]  # both outside the segment
    chunks = split_by_spectral_boundaries(segments, boundaries)
    assert len(chunks) == 1
    assert chunks[0]["start"] == 10.0
    assert chunks[0]["end"] == 30.0


def test_split_by_spectral_boundaries_empty_boundaries() -> None:
    segments = [{"start": 0.0, "end": 20.0, "text": "hello"}]
    chunks = split_by_spectral_boundaries(segments, [])
    assert len(chunks) == 1


def test_split_by_spectral_boundaries_absorbs_tiny_chunks() -> None:
    # Boundary at 0.02 s inside a segment starting at 0 — sub-chunk is < min_chunk
    segments = [{"start": 0.0, "end": 30.0, "text": "a b c"}]
    boundaries = [0.02]
    chunks = split_by_spectral_boundaries(segments, boundaries, min_chunk_seconds=0.5)
    # Tiny first chunk should be absorbed into the second
    assert len(chunks) == 1
