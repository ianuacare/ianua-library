"""Actual WAV slicing, resampling and bounds checks."""

import io

import pytest

from ianuacare.ai.parsers.audio_clips import iter_segment_clips
from ianuacare.core.exceptions.errors import ValidationError

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")


def test_stereo_resampling_and_split(tmp_path):
    path = tmp_path / "stereo.wav"
    sf.write(path, np.ones((48000 * 3, 2)) * 0.2, 48000)
    clips = list(iter_segment_clips(path, [{"start": 0.5, "end": 3}], max_clip_seconds=1))
    assert [c["duration"] for c in clips] == [1, 1, 0.5]
    assert [c["start"] for c in clips] == [0.5, 1.5, 2.5]
    for clip in clips:
        info = sf.info(io.BytesIO(clip["audio_bytes"]))
        assert (info.samplerate, info.channels, info.subtype) == (16000, 1, "PCM_16")
        samples, _ = sf.read(io.BytesIO(clip["audio_bytes"]))
        assert samples.mean() == pytest.approx(0.2, abs=0.001)


@pytest.mark.parametrize(
    "segment",
    [
        {"start": -1, "end": 1},
        {"start": 0, "end": 2},
        {"start": 1, "end": 0},
        {"start": 0, "end": float("nan")},
    ],
)
def test_invalid_bounds(segment):
    with pytest.raises(ValidationError):
        list(iter_segment_clips(np.zeros(16000), [segment]))


def test_encoded_bytes():
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(16000), 16000, format="WAV")
    clips = list(iter_segment_clips(buffer.getvalue(), [{"start": 0, "end": 1}]))
    assert clips[0]["duration"] == 1
