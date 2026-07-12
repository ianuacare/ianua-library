#!/usr/bin/env python3
"""Run transcription + diarization on a local audio file and print pipeline payloads.

Requirements:
  pip install -e ".[audio]"
  export OPENAI_API_KEY=sk-...     # Whisper via OpenAI

Usage:
  python scripts/run_diarization.py /path/to/session.wav
  python scripts/run_diarization.py /path/to/session.wav --num-speakers 2 --language it
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _json_dump(label: str, payload: Any) -> None:
    print(f"\n=== {label} ===\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _build_diarization_model(*, whisper_model: str):
    from ianuacare import (
        DiarizationModel,
        ModelOutNormalizer,
        SpeechTranscriptionProvider,
        Transcription,
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        print("Error: set OPENAI_API_KEY for Whisper transcription.", file=sys.stderr)
        sys.exit(1)

    provider = SpeechTranscriptionProvider(api_key=api_key.strip(), model=whisper_model)
    transcription = Transcription(provider, whisper_model, ModelOutNormalizer())
    return DiarizationModel(transcription=transcription)


def _run_via_orchestrator(model: Any, validated_input: dict[str, Any]) -> dict[str, Any]:
    from ianuacare.core.models.context import RequestContext
    from ianuacare.core.models.packet import DataPacket
    from ianuacare.core.models.user import User
    from ianuacare.core.orchestration.orchestrator import Orchestrator
    from ianuacare.core.orchestration.parser import InputDataParser, OutputDataParser

    user = User(user_id="cli", role="clinician", permissions=["pipeline:run"])
    context = RequestContext(
        user=user,
        product="local-test",
        metadata={"model_key": "diarization"},
    )
    packet = DataPacket(validated_data=validated_input)
    orchestrator = Orchestrator(
        InputDataParser(),
        OutputDataParser(),
        {"diarization": model},
        default_model_key="diarization",
    )
    orchestrator.execute(packet, context)
    return {
        "parsed_data": packet.parsed_data,
        "inference_result": packet.inference_result,
        "processed_data": packet.processed_data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe and diarize a local audio file.")
    parser.add_argument(
        "audio_path",
        type=Path,
        help="Path to .wav, .mp3, or other supported audio",
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=2,
        help="Number of speaker clusters for K-Means (default: 2)",
    )
    parser.add_argument("--language", default="it", help="Whisper language code (e.g. it, en)")
    parser.add_argument(
        "--merge-transcript-gaps",
        action="store_true",
        help="Merge Whisper segments when gap <= 1.5s (default: keep ASR granularity)",
    )
    parser.add_argument(
        "--max-segment-seconds",
        type=float,
        default=30.0,
        help="Split segments longer than this before speaker embedding (default: 30)",
    )
    parser.add_argument(
        "--no-spectral-split",
        action="store_true",
        help="Disable spectral change-point splitting; fall back to uniform time chunking",
    )
    parser.add_argument(
        "--spectral-threshold",
        type=float,
        default=0.35,
        help="Cosine-distance threshold for spectral boundary detection (default: 0.35; "
        "lower → more cuts, higher → fewer cuts)",
    )
    parser.add_argument(
        "--spectral-hop-seconds",
        type=float,
        default=2.0,
        help="Analysis window size in seconds for spectral features (default: 2.0)",
    )
    parser.add_argument(
        "--spectral-min-gap-seconds",
        type=float,
        default=1.5,
        help="Minimum gap between two spectral boundaries in seconds (default: 1.5)",
    )
    parser.add_argument("--whisper-model", default="whisper-1", help="OpenAI transcription model")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Call DiarizationModel only (skip Orchestrator wrappers)",
    )
    args = parser.parse_args()

    audio_path = args.audio_path.expanduser().resolve()
    if not audio_path.is_file():
        print(f"Error: audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    validated_input: dict[str, Any] = {
        "audio_path": str(audio_path),
        "language": args.language,
        "response_format": "verbose_json",
        "num_speakers": args.num_speakers,
        "merge_transcript_gaps": args.merge_transcript_gaps,
        "max_segment_seconds": args.max_segment_seconds,
        "use_spectral_split": not args.no_spectral_split,
        "spectral_threshold": args.spectral_threshold,
        "spectral_hop_seconds": args.spectral_hop_seconds,
        "spectral_min_gap_seconds": args.spectral_min_gap_seconds,
    }
    print(f"Audio: {audio_path}")
    print("Running transcription (Whisper) + diarization (spectral split + CAM++ + K-Means)...")

    model = _build_diarization_model(whisper_model=args.whisper_model)

    if args.direct:
        from ianuacare.core.orchestration.parser import InputDataParser

        packet_input = InputDataParser()._parse_impl(validated_input, model_key="diarization")
        _json_dump("Input to DiarizationModel (parsed_data)", packet_input)
        inference_result = model.run(packet_input)
        _json_dump("inference_result (payload verso il backend)", inference_result)
        return

    payloads = _run_via_orchestrator(model, validated_input)
    _json_dump("validated_data (come dal backend)", validated_input)
    _json_dump("parsed_data (dopo InputDataParser)", payloads["parsed_data"])
    _json_dump("inference_result (dopo DiarizationModel)", payloads["inference_result"])
    _json_dump("processed_data (dopo OutputDataParser)", payloads["processed_data"])

    print("\n--- Segmenti leggibili ---\n")
    result = payloads["inference_result"]
    if isinstance(result, dict):
        for seg in result.get("segments", []):
            if isinstance(seg, dict):
                sid = seg.get("speaker_id", "?")
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                text = seg.get("text", "")
                print(f"[speaker_{int(sid) + 1}] {start:.2f}s–{end:.2f}s: {text}")


if __name__ == "__main__":
    main()
