"""Core dictation pipeline logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from dictate.stt import SpeechToText

ResultStatus = Literal["ok", "empty", "too_short", "no_speech", "error"]


@dataclass(slots=True)
class TranscriptionResult:
    status: ResultStatus
    duration_s: float
    text: str = ""
    error: str | None = None


class DictationEngine:
    """Shared speech->text logic used by daemon and one-shot CLI."""

    def __init__(
        self,
        stt: SpeechToText,
        sample_rate: int = 16000,
        min_duration_s: float = 0.3,
    ):
        self.stt = stt
        self.sample_rate = sample_rate
        self.min_duration_s = min_duration_s

    def duration_s(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> TranscriptionResult:
        """Transcribe audio and classify common non-success outcomes."""
        if audio.size == 0:
            return TranscriptionResult(status="empty", duration_s=0.0)

        duration = self.duration_s(audio)
        if duration < self.min_duration_s:
            return TranscriptionResult(status="too_short", duration_s=duration)

        try:
            text = self.stt.transcribe(audio, language=language).strip()
        except Exception as exc:  # noqa: BLE001
            return TranscriptionResult(
                status="error",
                duration_s=duration,
                error=str(exc),
            )

        if not text:
            return TranscriptionResult(status="no_speech", duration_s=duration)

        return TranscriptionResult(status="ok", duration_s=duration, text=text)
