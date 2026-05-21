"""Spectral change-point detection for speaker turn segmentation.

Detects boundaries in an audio file where the short-term spectral
characteristics change abruptly — a reliable proxy for speaker turns,
topic shifts, and silence-to-speech transitions.

Algorithm
---------
1. Load the audio file at a fixed sample rate with librosa.
2. Compute MFCC features in non-overlapping *hop* windows.
3. Compute the cosine distance between each pair of adjacent windows.
4. Mark a boundary at every position where the distance exceeds *threshold*.
5. Enforce a minimum gap between consecutive boundaries to avoid spurious
   micro-segmentation.

All parameters are tunable and can be overridden per call.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ianuacare.core.exceptions.errors import InferenceError

if TYPE_CHECKING:  # pragma: no cover
    pass

_DEFAULT_SAMPLE_RATE = 16_000
_DEFAULT_HOP_SECONDS = 2.0
_DEFAULT_THRESHOLD = 0.35
_DEFAULT_MIN_GAP_SECONDS = 1.5
_N_MFCC = 20


def detect_spectral_boundaries(
    audio_path: str,
    *,
    hop_seconds: float = _DEFAULT_HOP_SECONDS,
    threshold: float = _DEFAULT_THRESHOLD,
    min_gap_seconds: float = _DEFAULT_MIN_GAP_SECONDS,
    sample_rate: int = _DEFAULT_SAMPLE_RATE,
) -> list[float]:
    """Return a sorted list of boundary timestamps (in seconds) for *audio_path*.

    Args:
        audio_path: Path to any audio file that librosa can read.
        hop_seconds: Duration of each analysis window in seconds.  Smaller
            values give finer granularity but more noise.  Recommended: 1–4 s.
        threshold: Cosine-distance threshold in [0, 1] above which a window
            boundary is promoted to a speaker boundary.  Lower → more cuts;
            higher → fewer cuts.  Recommended: 0.25–0.55.
        min_gap_seconds: Minimum time between two consecutive boundaries.
            Boundaries closer than this are collapsed (first one wins).
        sample_rate: Target sample rate for audio loading.

    Returns:
        Sorted list of boundary times in seconds, **not** including t=0 or
        the end of the file.  The caller decides how to use them as split
        points.

    Raises:
        InferenceError: When librosa or numpy are unavailable, or when the
            audio file cannot be read.
    """
    try:
        librosa = import_module("librosa")
        np = import_module("numpy")
    except ImportError as exc:
        raise InferenceError(
            "librosa and numpy are required for spectral segmentation; "
            'install with pip install -e ".[audio]"'
        ) from exc

    try:
        y, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    except Exception as exc:
        raise InferenceError(
            f"spectral segmenter could not load audio: {audio_path!r}"
        ) from exc

    total_duration = float(len(y)) / float(sr)
    if total_duration < hop_seconds * 2:
        return []

    hop_samples = max(1, int(hop_seconds * sr))
    n_windows = int(len(y)) // hop_samples

    # Build one MFCC vector per hop window
    vectors: list[Any] = []
    for i in range(n_windows):
        frame = y[i * hop_samples : (i + 1) * hop_samples]
        mfccs = librosa.feature.mfcc(y=frame, sr=sr, n_mfcc=_N_MFCC)
        vectors.append(mfccs.mean(axis=1))

    if len(vectors) < 2:
        return []

    matrix = np.stack(vectors)  # shape (n_windows, n_mfcc)

    # Cosine distance between adjacent windows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    normed = matrix / norms
    # dot product of row i with row i+1 → cosine similarity; distance = 1 - sim
    similarities = (normed[:-1] * normed[1:]).sum(axis=1)
    distances = 1.0 - similarities  # shape (n_windows - 1,)

    # Detect change points
    raw_boundaries: list[float] = []
    for idx, dist in enumerate(distances.tolist()):
        if dist >= threshold:
            # Boundary falls between window idx and idx+1
            t = float((idx + 1) * hop_samples) / float(sr)
            raw_boundaries.append(t)

    # Enforce minimum gap (collapse nearby boundaries)
    return _enforce_min_gap(raw_boundaries, min_gap_seconds=min_gap_seconds)


def _enforce_min_gap(boundaries: list[float], *, min_gap_seconds: float) -> list[float]:
    """Remove boundaries that are too close to the previous kept one."""
    kept: list[float] = []
    for t in sorted(boundaries):
        if not kept or t - kept[-1] >= min_gap_seconds:
            kept.append(t)
    return kept
