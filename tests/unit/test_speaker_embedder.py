"""Tests for SpeakerEmbedder payload validation."""

from __future__ import annotations

import pytest

from ianuacare.ai.models.inference.embedder import SpeakerEmbedder
from ianuacare.core.exceptions.errors import ValidationError


def test_run_requires_audio_path() -> None:
    with pytest.raises(ValidationError, match="audio_path"):
        SpeakerEmbedder().run({"start": 0.0, "end": 1.0})


def test_run_requires_mapping() -> None:
    with pytest.raises(ValidationError):
        SpeakerEmbedder().run("invalid")
