"""Speech-to-text backend adapters."""

from __future__ import annotations

import inspect
import logging
import os
import tempfile
import wave
from typing import Any, Literal

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

FasterWhisperModel = Literal[
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "turbo",
    "large-v3-turbo",
]
ComputeDevice = Literal["cpu", "cuda", "auto"]
ComputeType = Literal["int8", "float16", "float32"]
SttBackend = Literal["faster-whisper", "nemo-canary"]

DEFAULT_MODELS: dict[SttBackend, str] = {
    "faster-whisper": "turbo",
    "nemo-canary": "nvidia/canary-1b-flash",
}
NEMO_CANARY_MODELS = (
    "nvidia/canary-1b",
    "nvidia/canary-1b-flash",
    "nvidia/canary-1b-v2",
)


def _normalize_faster_whisper_model(model_size: str) -> str:
    if model_size == "large-v3-turbo":
        return "turbo"
    return model_size


class SpeechToText:
    """Base speech-to-text backend interface."""

    backend_name = "base"
    model_name = ""

    @property
    def model(self) -> Any:
        raise NotImplementedError

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        hotwords: str | None = None,
    ) -> str:
        raise NotImplementedError


class FasterWhisperSpeechToText(SpeechToText):
    """Low-latency transcription using faster-whisper."""

    backend_name = "faster-whisper"

    def __init__(
        self,
        model_size: str = "turbo",
        device: ComputeDevice = "auto",
        compute_type: ComputeType = "int8",
    ):
        self.model_name = _normalize_faster_whisper_model(model_size)
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "Loading faster-whisper model: %s (%s)",
                self.model_name,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_name,
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
        """Transcribe float32 16kHz mono audio to text."""
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


class NeMoCanarySpeechToText(SpeechToText):
    """NVIDIA NeMo Canary backend."""

    backend_name = "nemo-canary"

    def __init__(
        self,
        model_name: str = DEFAULT_MODELS["nemo-canary"],
        device: ComputeDevice = "auto",
    ):
        self.model_name = model_name
        self.device = device
        self._model: Any | None = None
        self._warned_hotwords = False

    @property
    def model(self) -> Any:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Any:
        logger.info("Loading NeMo model: %s", self.model_name)
        try:
            from nemo.collections.asr.models import ASRModel
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "NeMo backend requires nemo_toolkit[asr]. Install with: uv pip install '.[nemo]'"
            ) from exc

        loader_errors: list[str] = []
        model: Any | None = None

        for loader_name in ("ASRModel", "EncDecMultiTaskModel"):
            loader = self._resolve_loader(loader_name, ASRModel)
            if loader is None:
                continue
            try:
                model = self._load_with_fallback(loader)
                break
            except Exception as exc:  # noqa: BLE001
                loader_errors.append(f"{loader_name}: {exc}")

        if model is None:
            joined_errors = "; ".join(loader_errors) if loader_errors else "unknown loader failure"
            raise RuntimeError(
                f"Failed to load NeMo model '{self.model_name}': {joined_errors}"
            )

        if self.device == "cpu" and hasattr(model, "cpu"):
            model = model.cpu()
        if self.device == "cuda" and hasattr(model, "cuda"):
            model = model.cuda()
        if hasattr(model, "eval"):
            model.eval()

        logger.info("Model loaded")
        return model

    @staticmethod
    def _resolve_loader(loader_name: str, asr_model_cls: Any) -> Any | None:
        if loader_name == "ASRModel":
            return asr_model_cls.from_pretrained
        if loader_name == "EncDecMultiTaskModel":
            try:
                from nemo.collections.asr.models import EncDecMultiTaskModel
            except Exception:  # noqa: BLE001
                return None
            return EncDecMultiTaskModel.from_pretrained
        return None

    def _load_with_fallback(self, loader: Any) -> Any:
        if self.device == "cpu":
            try:
                return loader(self.model_name, map_location="cpu")
            except TypeError:
                return loader(self.model_name)
        return loader(self.model_name)

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        hotwords: str | None = None,
    ) -> str:
        if hotwords and not self._warned_hotwords:
            logger.warning(
                "Hotwords are not supported by the NeMo Canary backend yet; ignoring hotwords."
            )
            self._warned_hotwords = True

        wav_path = _write_temp_wav(audio)
        try:
            outputs = self._transcribe_path(wav_path, language=language)
            return self._extract_text(outputs).strip()
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _transcribe_path(self, wav_path: str, *, language: str | None) -> Any:
        transcribe_fn = self.model.transcribe
        params = inspect.signature(transcribe_fn).parameters
        kwargs: dict[str, Any] = {}

        if "batch_size" in params:
            kwargs["batch_size"] = 1
        if "pnc" in params:
            kwargs["pnc"] = "yes"
        if "source_lang" in params:
            kwargs["source_lang"] = language or "en"
        if "target_lang" in params:
            kwargs["target_lang"] = language or "en"

        return transcribe_fn([wav_path], **kwargs)

    @classmethod
    def _extract_text(cls, outputs: Any) -> str:
        if outputs is None:
            return ""
        if isinstance(outputs, str):
            return outputs
        if isinstance(outputs, dict):
            for key in ("text", "pred_text"):
                if key in outputs:
                    return str(outputs[key])
            return str(outputs)
        if isinstance(outputs, list):
            texts = [cls._extract_text(item).strip() for item in outputs]
            return " ".join(text for text in texts if text)
        if hasattr(outputs, "text"):
            return str(outputs.text)
        return str(outputs)


def _write_temp_wav(audio: np.ndarray, sample_rate: int = 16000) -> str:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(prefix="dictate-", suffix=".wav", delete=False) as temp:
        wav_path = temp.name

    with wave.open(wav_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())

    return wav_path


def create_speech_to_text(
    *,
    backend: SttBackend = "faster-whisper",
    model: str | None = None,
    device: ComputeDevice = "auto",
    compute_type: ComputeType = "int8",
) -> SpeechToText:
    model_name = model or DEFAULT_MODELS[backend]
    if backend == "faster-whisper":
        return FasterWhisperSpeechToText(
            model_size=model_name,
            device=device,
            compute_type=compute_type,
        )
    if backend == "nemo-canary":
        return NeMoCanarySpeechToText(model_name=model_name, device=device)
    raise ValueError(f"Unsupported STT backend: {backend}")
