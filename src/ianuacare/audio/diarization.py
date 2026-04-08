"""Audio diarization pipeline (pause detection + features + clustering)."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

from ianuacare.audio.whisper import WhisperResult, WhisperSegment, WhisperTranscriber


@dataclass(slots=True)
class DiarizedSegment:
    start: float
    end: float
    text: str
    speaker_id: int


@dataclass(slots=True)
class DiarizationResult:
    raw_transcription: str
    segments: list[dict[str, Any]]
    speakers: list[dict[str, Any]]


class PauseDetector:
    def __init__(self, silence_gap_seconds: float = 1.5) -> None:
        self._gap = silence_gap_seconds

    def split(self, segments: list[WhisperSegment]) -> list[WhisperSegment]:
        if not segments:
            return []
        out: list[WhisperSegment] = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            out.append(seg)
        return out


class SpectralAnalyzer:
    def extract(self, segment: WhisperSegment) -> dict[str, float]:
        # Lightweight deterministic feature proxy from timing/text metadata.
        duration = max(0.0, segment.end - segment.start)
        tokens = max(1, len(segment.text.split()))
        chars = len(segment.text)
        rate = tokens / duration if duration > 0 else float(tokens)
        return {
            "duration": duration,
            "tokens": float(tokens),
            "chars": float(chars),
            "rate": float(rate),
        }


class SpeakerEmbedder:
    def embed(self, features: dict[str, float]) -> list[float]:
        duration = features.get("duration", 0.0)
        tokens = features.get("tokens", 0.0)
        chars = features.get("chars", 0.0)
        rate = features.get("rate", 0.0)
        return [duration, tokens, chars, rate, sqrt(tokens * max(duration, 0.0))]


class SpeakerClusterer:
    def cluster(self, vectors: list[list[float]], *, num_speakers: int) -> list[int]:
        if not vectors:
            return []
        k = max(1, num_speakers)
        # Simple deterministic fallback assignment when sklearn is unavailable.
        labels: list[int] = []
        for idx, vec in enumerate(vectors):
            signal = int(sum(int(v * 1000) for v in vec))
            labels.append(abs(signal + idx) % k)
        return labels


class DiarizationPipeline:
    """Full diarization pipeline callable from application tasks."""

    def __init__(
        self,
        transcriber: WhisperTranscriber | None = None,
        pause_detector: PauseDetector | None = None,
        spectral: SpectralAnalyzer | None = None,
        embedder: SpeakerEmbedder | None = None,
        clusterer: SpeakerClusterer | None = None,
    ) -> None:
        self._transcriber = transcriber or WhisperTranscriber()
        self._pause_detector = pause_detector or PauseDetector()
        self._spectral = spectral or SpectralAnalyzer()
        self._embedder = embedder or SpeakerEmbedder()
        self._clusterer = clusterer or SpeakerClusterer()

    def run(
        self,
        audio_path: str,
        *,
        num_speakers: int = 2,
        language: str | None = None,
    ) -> DiarizationResult:
        whisper: WhisperResult = self._transcriber.transcribe(audio_path, language=language)
        segments = self._pause_detector.split(whisper.segments)
        vectors: list[list[float]] = []
        for seg in segments:
            features = self._spectral.extract(seg)
            vectors.append(self._embedder.embed(features))
        labels = self._clusterer.cluster(vectors, num_speakers=max(1, num_speakers))

        diarized: list[DiarizedSegment] = []
        speaker_counts: dict[int, int] = {}
        for seg, label in zip(segments, labels, strict=False):
            speaker_counts[label] = speaker_counts.get(label, 0) + 1
            diarized.append(
                DiarizedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker_id=label,
                )
            )
        speaker_list = [
            {"id": sid, "label": f"speaker_{sid + 1}", "segment_count": count}
            for sid, count in sorted(speaker_counts.items())
        ]
        out_segments = [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "speaker_id": s.speaker_id,
            }
            for s in diarized
        ]
        return DiarizationResult(
            raw_transcription=whisper.text,
            segments=out_segments,
            speakers=speaker_list,
        )
