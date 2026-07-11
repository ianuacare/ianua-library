"""Diarization model composed from transcription + parsers + clustering."""

from __future__ import annotations

from typing import Any

from ianuacare.ai._numeric import to_float
from ianuacare.ai.models.inference.base import BaseAIModel
from ianuacare.ai.models.inference.campp_embedder import CamPlusPlusEmbedder
from ianuacare.ai.models.inference.clusterer import SpeakerClusterer
from ianuacare.ai.models.inference.transcription import Transcription
from ianuacare.ai.parsers.pause import PauseParser
from ianuacare.ai.parsers.segment_duration import (
    DEFAULT_MAX_SEGMENT_SECONDS,
    DEFAULT_MIN_EMBEDDING_SECONDS,
    merge_labeled_chunks,
    merge_short_chunks,
    split_by_max_duration,
    split_by_spectral_boundaries,
)
from ianuacare.ai.parsers.spectral_segmenter import (
    _DEFAULT_HOP_SECONDS,
    _DEFAULT_MIN_GAP_SECONDS,
    _DEFAULT_THRESHOLD,
    detect_spectral_boundaries,
)


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
        embedder: BaseAIModel | None = None,
        clusterer: SpeakerClusterer | None = None,
        *,
        merge_transcript_gaps: bool = False,
        max_segment_seconds: float = DEFAULT_MAX_SEGMENT_SECONDS,
        use_spectral_split: bool = True,
        spectral_hop_seconds: float = _DEFAULT_HOP_SECONDS,
        spectral_threshold: float = _DEFAULT_THRESHOLD,
        spectral_min_gap_seconds: float = _DEFAULT_MIN_GAP_SECONDS,
        min_embedding_seconds: float = DEFAULT_MIN_EMBEDDING_SECONDS,
    ) -> None:
        self._transcription = transcription
        self._pause_parser = pause_parser or PauseParser(merge_gaps=merge_transcript_gaps)
        # Default to the neural CAM++ embedder (MFCC SpeakerEmbedder remains
        # available for callers that inject it explicitly).
        self._embedder: BaseAIModel = embedder or CamPlusPlusEmbedder()
        self._clusterer = clusterer or SpeakerClusterer()
        self._merge_transcript_gaps = merge_transcript_gaps
        self._max_segment_seconds = max_segment_seconds
        self._use_spectral_split = use_spectral_split
        self._spectral_hop_seconds = spectral_hop_seconds
        self._spectral_threshold = spectral_threshold
        self._spectral_min_gap_seconds = spectral_min_gap_seconds
        self._min_embedding_seconds = min_embedding_seconds

    def run(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"raw_transcription": "", "segments": [], "speakers": []}

        transcript = self._run_transcription(payload)
        segments = transcript.get("segments", [])
        if not isinstance(segments, list):
            segments = []

        merge_gaps = self._resolve_merge_gaps(payload)
        max_segment_seconds = self._resolve_max_segment_seconds(payload)
        normalized = self._pause_parser.parse(segments, merge_gaps=merge_gaps)

        use_spectral = bool(payload.get("use_spectral_split", self._use_spectral_split))

        if use_spectral:
            audio_path_for_split = payload.get("audio_path")
            embedding_segments = self._split_spectral(
                normalized,
                audio_path=audio_path_for_split if isinstance(audio_path_for_split, str) else "",
                payload=payload,
            )
        else:
            embedding_segments = split_by_max_duration(
                normalized,
                max_duration_seconds=max_segment_seconds,
            )

        # Consolidate micro-turns so each window carries enough speech for a
        # stable neural (CAM++) embedding.
        embedding_segments = merge_short_chunks(
            embedding_segments,
            min_seconds=self._resolve_min_embedding_seconds(payload),
        )

        audio_path = payload.get("audio_path")
        if not isinstance(audio_path, str) or not audio_path.strip():
            return {
                "raw_transcription": str(transcript.get("text", "")),
                "segments": [],
                "speakers": [],
            }

        embed_payload: dict[str, Any] = {
            "audio_path": audio_path.strip(),
            "segments": [
                {
                    "start": to_float(segment.get("start"), 0.0),
                    "end": to_float(segment.get("end"), to_float(segment.get("start"), 0.0)),
                }
                for segment in embedding_segments
            ],
        }
        embedded = self._embedder.run(embed_payload)
        vectors: list[list[float]] = []
        if isinstance(embedded, list) and embedded:
            if isinstance(embedded[0], list):
                vectors = [list(vector) for vector in embedded]
            elif isinstance(embedded[0], int | float):
                vectors = [[float(component) for component in embedded]]

        cluster_payload: dict[str, Any] = {"vectors": vectors}
        if "num_speakers" in payload:
            cluster_payload["num_speakers"] = payload.get("num_speakers")

        labels = self._clusterer.run(cluster_payload)
        labels = _align_labels(labels, len(embedding_segments))
        diarized_segments = merge_labeled_chunks(
            embedding_segments,
            labels,
            merge_consecutive=True,
        )

        speaker_counts: dict[int, int] = {}
        for segment in diarized_segments:
            speaker_id = int(segment.get("speaker_id", 0))
            speaker_counts[speaker_id] = speaker_counts.get(speaker_id, 0) + 1

        speakers = [
            {"id": sid, "label": f"speaker_{sid + 1}", "segment_count": count}
            for sid, count in sorted(speaker_counts.items())
        ]
        return {
            "raw_transcription": str(transcript.get("text", "")),
            "segments": diarized_segments,
            "speakers": speakers,
        }

    def _split_spectral(
        self,
        normalized: list[dict[str, Any]],
        *,
        audio_path: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compute spectral boundaries and split segments; fall back to duration split on error."""
        hop = to_float(payload.get("spectral_hop_seconds"), self._spectral_hop_seconds)
        threshold = to_float(payload.get("spectral_threshold"), self._spectral_threshold)
        min_gap = to_float(payload.get("spectral_min_gap_seconds"), self._spectral_min_gap_seconds)
        max_dur = self._resolve_max_segment_seconds(payload)

        if not audio_path.strip():
            return split_by_max_duration(normalized, max_duration_seconds=max_dur)

        try:
            boundaries = detect_spectral_boundaries(
                audio_path.strip(),
                hop_seconds=hop,
                threshold=threshold,
                min_gap_seconds=min_gap,
            )
        except Exception:
            # Non-fatal: fall back to uniform time splitting
            return split_by_max_duration(normalized, max_duration_seconds=max_dur)

        chunks = split_by_spectral_boundaries(normalized, boundaries)

        # Still apply duration cap on the result so a single sparse chunk
        # between two boundaries cannot be arbitrarily long
        return split_by_max_duration(chunks, max_duration_seconds=max_dur)

    def _resolve_merge_gaps(self, payload: dict[str, Any]) -> bool:
        if "merge_transcript_gaps" in payload:
            return bool(payload.get("merge_transcript_gaps"))
        return self._merge_transcript_gaps

    def _resolve_max_segment_seconds(self, payload: dict[str, Any]) -> float:
        if "max_segment_seconds" in payload:
            return max(0.0, to_float(payload.get("max_segment_seconds"), self._max_segment_seconds))
        return self._max_segment_seconds

    def _resolve_min_embedding_seconds(self, payload: dict[str, Any]) -> float:
        if "min_embedding_seconds" in payload:
            return max(
                0.0, to_float(payload.get("min_embedding_seconds"), self._min_embedding_seconds)
            )
        return self._min_embedding_seconds

    def _run_transcription(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._transcription is None:
            return {"text": "", "segments": []}
        return self._transcription.run(payload)
