"""Core dictation pipeline logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from dictate.lexicon import (
    LexiconMode,
    apply_post_corrections,
    build_lexicon_plan,
    normalize_lexicon_mode,
)
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
        hotwords: str | None = None,
        lexicon_mode: LexiconMode = "native",
        lexicon_replacements: dict[str, str] | None = None,
    ):
        self.stt = stt
        self.sample_rate = sample_rate
        self.min_duration_s = min_duration_s
        self.hotwords = hotwords
        self.lexicon_mode = normalize_lexicon_mode(lexicon_mode)
        self.lexicon_replacements = dict(lexicon_replacements or {})

    @property
    def supports_hotwords(self) -> bool:
        return self.stt.capabilities.supports_hotwords

    def set_hotwords(self, hotwords: str | None) -> None:
        self.hotwords = hotwords

    def set_lexicon_mode(self, lexicon_mode: LexiconMode) -> None:
        self.lexicon_mode = normalize_lexicon_mode(lexicon_mode)

    def set_lexicon_replacements(self, replacements: dict[str, str] | None) -> None:
        self.lexicon_replacements = dict(replacements or {})

    def duration_s(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> TranscriptionResult:
        """Transcribe audio and classify common non-success outcomes."""
        if audio.size == 0:
            return TranscriptionResult(status="empty", duration_s=0.0)

        duration = self.duration_s(audio)
        if duration < self.min_duration_s:
            return TranscriptionResult(status="too_short", duration_s=duration)

        lexicon_plan = build_lexicon_plan(
            stt=self.stt,
            hotwords=self.hotwords,
            lexicon_mode=self.lexicon_mode,
            replacements=self.lexicon_replacements,
        )
        try:
            text = self.stt.transcribe(
                audio,
                language=language,
                hotwords=lexicon_plan.decode_hotwords,
                prompt_context=lexicon_plan.prompt_context,
            ).strip()
        except Exception as exc:  # noqa: BLE001
            return TranscriptionResult(
                status="error",
                duration_s=duration,
                error=str(exc),
            )

        if lexicon_plan.post_hotwords or lexicon_plan.post_replacements:
            text = apply_post_corrections(
                text,
                hotwords=lexicon_plan.post_hotwords,
                replacements=lexicon_plan.post_replacements,
            ).strip()

        if not text:
            return TranscriptionResult(status="no_speech", duration_s=duration)

        return TranscriptionResult(status="ok", duration_s=duration, text=text)
