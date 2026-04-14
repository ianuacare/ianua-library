"""Diarization model composed from transcription + parsers + clustering."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float, to_positive_int
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.clusterer import SpeakerClusterer
from ianuacare.ai.models.inference.embedder import SpeakerEmbedder
from ianuacare.ai.models.inference.transcription import Transcription
from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.parsers.spectral import SpectralParser


def _align_labels(labels: list[int], n: int) -> list[int]:
    """Ensure one label per segment; pad or trim defensively."""
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


class DiarizationModel(BaseAIModel):
    """Run full diarization from audio path and model dependencies."""

    def __init__(
        self,
        transcription: Transcription | None = None,
        pause_parser: PauseParser | None = None,
        spectral_parser: SpectralParser | None = None,
        embedder: SpeakerEmbedder | None = None,
        clusterer: SpeakerClusterer | None = None,
    ) -> None:
        self._transcription = transcription
        self._pause_parser = pause_parser or PauseParser()
        self._spectral_parser = spectral_parser or SpectralParser()
        self._embedder = embedder or SpeakerEmbedder()
        self._clusterer = clusterer or SpeakerClusterer()

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"raw_transcription": "", "segments": [], "speakers": []}

        transcript = self._run_transcription(payload)
        segments = transcript.get("segments", [])
        if not isinstance(segments, list):
            segments = []
        split_segments = self._pause_parser.parse(segments)

        vectors: list[list[float]] = []
        for segment in split_segments:
            features = self._spectral_parser.parse(segment)
            vectors.append(self._embedder.run(features))

        num_speakers = to_positive_int(payload.get("num_speakers"), default=2)
        labels = self._clusterer.run({"vectors": vectors, "num_speakers": num_speakers})
        labels = _align_labels(labels, len(split_segments))
        diarized_segments: list[dict[str, Any]] = []
        speaker_counts: dict[int, int] = {}
        for segment, label in zip(split_segments, labels, strict=True):
            speaker_counts[label] = speaker_counts.get(label, 0) + 1
            seg_start = to_float(segment.get("start"), 0.0)
            diarized_segments.append(
                {
                    "start": seg_start,
                    "end": to_float(segment.get("end"), seg_start),
                    "text": str(segment.get("text", "")).strip(),
                    "speaker_id": label,
                }
            )

        speakers = [
            {"id": sid, "label": f"speaker_{sid + 1}", "segment_count": count}
            for sid, count in sorted(speaker_counts.items())
        ]
        return {
            "raw_transcription": str(transcript.get("text", "")),
            "segments": diarized_segments,
            "speakers": speakers,
        }

    def _run_transcription(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._transcription is None:
            return {"text": "", "segments": []}
        return self._transcription.run(payload)
