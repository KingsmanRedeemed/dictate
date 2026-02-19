from __future__ import annotations

import unittest

import numpy as np

from dictate.engine import DictationEngine
from dictate.stt import SpeechToText, SttCapabilities


class _DummyNoHotwordsSpeechToText(SpeechToText):
    backend_name = "dummy-no-hotwords"
    capabilities = SttCapabilities(supports_hotwords=False)

    def __init__(self) -> None:
        self.received_hotwords: str | None = None

    @property
    def model(self):
        return None

    def transcribe(self, audio, language=None, hotwords=None) -> str:
        del audio, language
        self.received_hotwords = hotwords
        return "ok"


class _DummyHotwordsSpeechToText(SpeechToText):
    backend_name = "dummy-hotwords"
    capabilities = SttCapabilities(supports_hotwords=True)

    def __init__(self) -> None:
        self.received_hotwords: str | None = None

    @property
    def model(self):
        return None

    def transcribe(self, audio, language=None, hotwords=None) -> str:
        del audio, language
        self.received_hotwords = hotwords
        return "ok"


class DictationEngineCapabilityTests(unittest.TestCase):
    def test_hotwords_dropped_when_backend_does_not_support_them(self) -> None:
        stt = _DummyNoHotwordsSpeechToText()
        engine = DictationEngine(stt=stt, hotwords="OpenBao Kubernetes")
        audio = np.ones(8000, dtype=np.float32)

        result = engine.transcribe(audio, language="en")

        self.assertEqual(result.status, "ok")
        self.assertIsNone(stt.received_hotwords)

    def test_hotwords_passed_when_backend_supports_them(self) -> None:
        stt = _DummyHotwordsSpeechToText()
        engine = DictationEngine(stt=stt, hotwords="OpenBao Kubernetes")
        audio = np.ones(8000, dtype=np.float32)

        result = engine.transcribe(audio, language="en")

        self.assertEqual(result.status, "ok")
        self.assertEqual(stt.received_hotwords, "OpenBao Kubernetes")


if __name__ == "__main__":
    unittest.main()
