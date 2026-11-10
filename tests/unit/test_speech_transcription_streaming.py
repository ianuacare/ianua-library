"""Streaming split of large audio files in SpeechTranscriptionProvider (issue #23)."""

from __future__ import annotations

import logging
import math
import shutil
import subprocess
import tempfile
import tracemalloc
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from ianuacare.ai.providers import speech_transcription as speech_module
from ianuacare.ai.providers.speech_transcription import SpeechTranscriptionProvider


class _Obj:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _RecordingClient:
    """Fake OpenAI client: records each uploaded chunk and answers with local times."""

    def __init__(self, *, decode: bool = True) -> None:
        self.calls: list[dict[str, Any]] = []
        self._decode = decode
        self.audio = _Obj(transcriptions=_Obj(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        handle = kwargs["file"]
        call: dict[str, Any] = {"kwargs": kwargs}
        if self._decode:
            data, sr = sf.read(handle, dtype="float32", always_2d=True)
            call.update(frames=len(data), samplerate=sr, channels=data.shape[1], data=data[:, 0])
        else:
            info = sf.info(handle)
            call.update(frames=info.frames, samplerate=info.samplerate, channels=info.channels)
        index = len(self.calls)
        self.calls.append(call)
        return _Obj(
            text=f"part{index}",
            segments=[_Obj(start=0.25, end=0.75, text=f" seg{index} ")],
            words=[_Obj(start=0.5, end=0.6, word=f"w{index}")],
        )


def _transcribe(provider: SpeechTranscriptionProvider, path: Path) -> dict[str, Any]:
    return provider._transcribe_chunked(
        "whisper-1",
        str(path),
        language="it",
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"],
    )


def _chunk_frames(frames: int) -> Any:
    """Shrink the per-chunk budget so small fixtures still span several chunks."""
    return patch.object(
        SpeechTranscriptionProvider, "_max_samples_per_wav_chunk", return_value=frames
    )


def _sine(frames: int, sr: int, freq: float = 220.0) -> np.ndarray:
    t = np.arange(frames, dtype=np.float64) / sr
    return (0.3 * np.sin(2 * math.pi * freq * t)).astype(np.float32)


@pytest.mark.parametrize(
    ("sr", "channels"),
    [(16_000, 1), (48_000, 2)],
)
def test_streaming_split_chunk_count_offsets_and_merge(
    tmp_path: Path, sr: int, channels: int
) -> None:
    max_samples = sr  # one-second chunks keep the fixture tiny
    total = int(sr * 3.5)
    mono = _sine(total, sr)
    source = np.stack([mono] * channels, axis=1) if channels > 1 else mono
    path = tmp_path / "in.wav"
    sf.write(path, source, sr, subtype="PCM_16")

    client = _RecordingClient()
    provider = SpeechTranscriptionProvider(client=client)
    with _chunk_frames(max_samples):
        out = _transcribe(provider, path)

    expected_chunks = math.ceil(total / max_samples)  # same count as the old in-memory split
    assert len(client.calls) == expected_chunks
    assert [c["frames"] for c in client.calls] == [max_samples] * 3 + [total - 3 * max_samples]
    assert all(c["samplerate"] == sr and c["channels"] == 1 for c in client.calls)
    assert all(c["kwargs"]["language"] == "it" for c in client.calls)

    # Downmixed PCM_16 content matches the source, chunk by chunk.
    rebuilt = np.concatenate([c["data"] for c in client.calls])
    np.testing.assert_allclose(rebuilt, mono, atol=2 / 32768)

    offsets = [i * max_samples / sr for i in range(expected_chunks)]
    assert out["text"] == "part0 part1 part2 part3"
    assert out["segments"] == [
        {"start": o + 0.25, "end": o + 0.75, "text": f"seg{i}"} for i, o in enumerate(offsets)
    ]
    assert out["words"] == [
        {"start": o + 0.5, "end": o + 0.6, "text": f"w{i}"} for i, o in enumerate(offsets)
    ]


def test_streaming_split_empty_file_keeps_legacy_shape(tmp_path: Path) -> None:
    path = tmp_path / "empty.wav"
    sf.write(path, np.zeros(0, dtype=np.float32), 16_000, subtype="PCM_16")
    client = _RecordingClient()

    out = _transcribe(SpeechTranscriptionProvider(client=client), path)

    assert out == {"text": "", "segments": []}
    assert client.calls == []


def test_chunk_files_are_removed_after_upload(tmp_path: Path) -> None:
    path = tmp_path / "in.wav"
    sf.write(path, _sine(16_000 * 3, 16_000), 16_000, subtype="PCM_16")
    seen: list[str] = []

    class _Client(_RecordingClient):
        def _create(self, **kwargs: Any) -> Any:
            seen.append(kwargs["file"].name)
            return super()._create(**kwargs)

    provider = SpeechTranscriptionProvider(client=_Client())
    with _chunk_frames(16_000):
        _transcribe(provider, path)

    assert len(seen) == 3
    assert not any(Path(p).exists() for p in seen)


_FFMPEG = shutil.which("ffmpeg")
_needs_ffmpeg = pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg not installed")
_MODULE = "ianuacare.ai.providers.speech_transcription"


def _ffmpeg_encode(source: Path, target: Path) -> None:
    assert _FFMPEG is not None
    subprocess.run(
        [_FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-i", str(source), str(target)],
        check=True,
    )


@_needs_ffmpeg
@pytest.mark.parametrize("suffix", ["mp3", "ogg", "m4a"])
def test_lossy_formats_are_always_normalized_with_ffmpeg(tmp_path: Path, suffix: str) -> None:
    """MP3/OGG open fine in libsndfile, but are still transcoded: no mid-decode failures."""
    sr = 44_100
    stereo = np.stack([_sine(sr * 3, sr)] * 2, axis=1)
    path = tmp_path / f"in.{suffix}"
    if suffix == "ogg":  # Vorbis written by libsndfile itself, so soundfile can open it
        sf.write(path, stereo, sr, format="OGG", subtype="VORBIS")
    else:
        wav = tmp_path / "src.wav"
        sf.write(wav, stereo, sr, subtype="PCM_16")
        _ffmpeg_encode(wav, path)

    client = _RecordingClient()
    provider = SpeechTranscriptionProvider(client=client)
    convert = speech_module._convert_with_ffmpeg
    with (
        patch(f"{_MODULE}._convert_with_ffmpeg", side_effect=convert) as spy,
        _chunk_frames(16_000),
    ):
        out = _transcribe(provider, path)

    spy.assert_called_once()
    assert {c["samplerate"] for c in client.calls} == {16_000}
    assert all(c["channels"] == 1 for c in client.calls)
    assert out["segments"][0]["start"] == 0.25
    assert out["segments"][1]["start"] == 1.25


@pytest.mark.parametrize(
    ("suffix", "fmt"),
    [("wav", "WAV"), ("wav", "WAVEX"), ("flac", "FLAC"), ("aiff", "AIFF")],
)
def test_lossless_formats_are_streamed_without_ffmpeg(
    tmp_path: Path, suffix: str, fmt: str
) -> None:
    sr = 22_050
    path = tmp_path / f"in.{suffix}"
    sf.write(path, _sine(sr * 2, sr), sr, format=fmt, subtype="PCM_16")
    client = _RecordingClient()

    with (
        patch(f"{_MODULE}._convert_with_ffmpeg", side_effect=AssertionError("no ffmpeg")),
        _chunk_frames(sr),
    ):
        _transcribe(SpeechTranscriptionProvider(client=client), path)

    assert [(c["samplerate"], c["frames"]) for c in client.calls] == [(sr, sr), (sr, sr)]


def test_ffmpeg_timeout_raises_and_removes_partial_output(tmp_path: Path) -> None:
    path = tmp_path / "in.mp3"
    path.write_bytes(b"pretend mp3")
    targets: list[Path] = []
    seen_timeouts: list[float] = []

    def _slow_ffmpeg(command: list[str], **kwargs: Any) -> Any:
        target = Path(command[-1])
        target.write_bytes(b"RIFF partial")
        targets.append(target)
        seen_timeouts.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    provider = SpeechTranscriptionProvider(client=_RecordingClient(), ffmpeg_timeout_seconds=42)
    with (
        patch(f"{_MODULE}.shutil.which", return_value="/usr/bin/ffmpeg"),
        patch(f"{_MODULE}.subprocess.run", side_effect=_slow_ffmpeg),
        pytest.raises(ValueError, match="ffmpeg timed out after 42s"),
    ):
        _transcribe(provider, path)

    assert seen_timeouts == [42]
    assert len(targets) == 1 and not targets[0].exists()


def test_ffmpeg_timeout_has_a_generous_default() -> None:
    provider = SpeechTranscriptionProvider(client=_RecordingClient())
    assert provider._ffmpeg_timeout_seconds == 900.0


def test_chunk_generator_is_closed_before_temp_dir_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "in.wav"
    sf.write(path, _sine(16_000 * 3, 16_000), 16_000, subtype="PCM_16")
    events: list[str] = []
    real_iter = SpeechTranscriptionProvider._iter_wav_chunks
    # Keep the generator referenced (as a traceback, debugger or non-refcounting
    # interpreter would): only an explicit close() can release the source file.
    alive: list[Any] = []

    def _gen(self: Any, *args: Any) -> Any:
        try:
            yield from real_iter(self, *args)
        finally:
            events.append("generator closed")

    def _tracked(self: Any, *args: Any) -> Any:
        alive.append(_gen(self, *args))
        return alive[-1]

    class _TrackedTempDir(tempfile.TemporaryDirectory):
        def __exit__(self, *exc: Any) -> None:
            events.append("temp dir removed")
            super().__exit__(*exc)

    class _FailingClient(_RecordingClient):
        def _create(self, **kwargs: Any) -> Any:
            if self.calls:
                raise RuntimeError("API down")
            return super()._create(**kwargs)

    provider = SpeechTranscriptionProvider(client=_FailingClient())
    with (
        patch.object(SpeechTranscriptionProvider, "_iter_wav_chunks", _tracked),
        patch(f"{_MODULE}.tempfile.TemporaryDirectory", _TrackedTempDir),
        _chunk_frames(16_000),
        pytest.raises(RuntimeError, match="API down"),
    ):
        _transcribe(provider, path)

    assert events == ["generator closed", "temp dir removed"]


def test_max_samples_per_chunk_caps_duration_at_low_sample_rates() -> None:
    byte_frames = SpeechTranscriptionProvider._max_samples_per_wav_chunk()
    assert byte_frames == (24 * 1024 * 1024 - 4096) // 2
    assert SpeechTranscriptionProvider._max_samples_per_wav_chunk(16_000) == byte_frames
    assert SpeechTranscriptionProvider._max_samples_per_wav_chunk(8_000) == 8_000 * 1200


def test_8khz_wav_chunks_never_exceed_1200_seconds(tmp_path: Path) -> None:
    """25 min at 8 kHz fits the byte budget in one ~26 min chunk without the cap."""
    sr = 8_000
    path = tmp_path / "phone.wav"
    minute = _sine(sr * 60, sr)
    with sf.SoundFile(path, mode="w", samplerate=sr, channels=1, subtype="PCM_16") as sink:
        for _ in range(25):
            sink.write(minute)
    client = _RecordingClient(decode=False)

    out = _transcribe(SpeechTranscriptionProvider(client=client), path)

    assert [c["frames"] for c in client.calls] == [sr * 1200, sr * 300]
    assert [s["start"] for s in out["segments"]] == [0.25, 1200.25]


def test_falls_back_to_in_memory_decode_without_ffmpeg(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "in.wav"
    sf.write(path, _sine(16_000 * 2, 16_000), 16_000, subtype="PCM_16")
    client = _RecordingClient()
    provider = SpeechTranscriptionProvider(client=client)

    with (
        patch("soundfile.info", side_effect=RuntimeError("unsupported")),
        patch(f"{_MODULE}.shutil.which", return_value=None),
        _chunk_frames(16_000),
        caplog.at_level(logging.WARNING, logger="ianuacare.ai.providers.speech_transcription"),
    ):
        out = _transcribe(provider, path)

    assert len(client.calls) == 2
    assert [s["start"] for s in out["segments"]] == [0.25, 1.25]
    assert "decoding the whole file in memory" in caplog.text


def test_ffmpeg_decode_failure_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.mp3"
    path.write_bytes(b"not really audio" * 1024)
    if _FFMPEG is None:
        pytest.skip("ffmpeg not installed")

    with pytest.raises(ValueError, match="ffmpeg could not decode"):
        _transcribe(SpeechTranscriptionProvider(client=_RecordingClient()), path)


def test_two_hour_wav_split_stays_within_memory_budget(tmp_path: Path) -> None:
    """2 h of 16 kHz mono PCM_16 (~230 MB on disk) must not be decoded in one go."""
    sr = 16_000
    hours = 2
    path = tmp_path / "meeting_2h.wav"
    minute = _sine(sr * 60, sr)
    with sf.SoundFile(path, mode="w", samplerate=sr, channels=1, subtype="PCM_16") as sink:
        for _ in range(hours * 60):
            sink.write(minute)
    del minute

    client = _RecordingClient(decode=False)
    provider = SpeechTranscriptionProvider(client=client)

    tracemalloc.start()
    try:
        out = _transcribe(provider, path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    total = sr * 3600 * hours
    max_samples = SpeechTranscriptionProvider._max_samples_per_wav_chunk()
    assert len(client.calls) == math.ceil(total / max_samples)
    assert sum(c["frames"] for c in client.calls) == total
    assert out["segments"][-1]["start"] == pytest.approx(
        (len(client.calls) - 1) * max_samples / sr + 0.25
    )
    print(f"tracemalloc peak during 2h split: {peak / 1024 / 1024:.1f} MiB")
    assert peak < 300 * 1024 * 1024
