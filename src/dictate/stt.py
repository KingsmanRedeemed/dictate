"""Speech-to-text using faster-whisper. Extracted from iris-by-arc-forge."""

import logging
from typing import Literal

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

ModelSize = Literal["tiny", "base", "small", "medium", "large-v3", "turbo"]


class SpeechToText:
    """
    Low-latency transcription using faster-whisper with int8 quantization.

    Performance (RTX 4090, base model, int8):
        2s audio: ~22ms (beam=1), ~43ms (beam=5)
        6s audio: ~55ms (beam=1), ~87ms (beam=5)
    """

    def __init__(
        self,
        model_size: ModelSize = "base",
        device: Literal["cpu", "cuda", "auto"] = "auto",
        compute_type: Literal["int8", "float16", "float32"] = "int8",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_size} ({self.compute_type})")
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Model loaded")
        return self._model

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        hotwords: str | None = None,
    ) -> str:
        """Transcribe float32 16kHz audio to text."""
        segments, _info = self.model.transcribe(
            audio,
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
            hotwords=hotwords,
        )
        return " ".join(seg.text.strip() for seg in segments)
