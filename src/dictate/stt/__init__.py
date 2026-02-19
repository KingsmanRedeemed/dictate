"""Speech-to-text backend exports."""

from dictate.stt.base import (
    ComputeDevice,
    ComputeType,
    FasterWhisperModel,
    SpeechToText,
    SttBackend,
    SttCapabilities,
)
from dictate.stt.factory import (
    BACKEND_REGISTRY,
    DEFAULT_MODELS,
    FASTER_WHISPER_MODELS,
    NEMO_CANARY_MODELS,
    STT_BACKENDS,
    BackendReadiness,
    check_backend_readiness,
    create_speech_to_text,
    resolve_model_name,
)
from dictate.stt.faster_whisper_backend import FasterWhisperSpeechToText
from dictate.stt.nemo_canary_backend import NeMoCanarySpeechToText

__all__ = [
    "BACKEND_REGISTRY",
    "DEFAULT_MODELS",
    "FASTER_WHISPER_MODELS",
    "NEMO_CANARY_MODELS",
    "STT_BACKENDS",
    "BackendReadiness",
    "ComputeDevice",
    "ComputeType",
    "FasterWhisperModel",
    "FasterWhisperSpeechToText",
    "NeMoCanarySpeechToText",
    "SpeechToText",
    "SttBackend",
    "SttCapabilities",
    "check_backend_readiness",
    "create_speech_to_text",
    "resolve_model_name",
]
