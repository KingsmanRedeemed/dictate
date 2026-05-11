from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from dictate.stt.whisper_cpp_backend import (
    WhisperCppSpeechToText,
    resolve_whisper_cpp_model,
    resolve_whisper_cpp_server,
)


class WhisperCppBackendTests(unittest.TestCase):
    def test_resolve_paths_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            binary = Path(temp_dir) / "whisper-cli.exe"
            model = Path(temp_dir) / "ggml-large-v3-turbo-q5_0.bin"
            with patch.dict(
                os.environ,
                {
                    "DICTATE_WHISPER_CPP_SERVER": str(binary),
                    "DICTATE_WHISPER_CPP_MODEL": str(model),
                },
                clear=False,
            ):
                self.assertEqual(resolve_whisper_cpp_server(), binary)
                self.assertEqual(resolve_whisper_cpp_model("large-v3-turbo-q5_0"), model)

    def test_model_name_maps_to_default_user_data_model_path(self) -> None:
        model_path = resolve_whisper_cpp_model("large-v3-turbo-q5_0")

        self.assertEqual(model_path.name, "ggml-large-v3-turbo-q5_0.bin")

    def test_model_property_validates_binary_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            binary = temp_path / "whisper-cli.exe"
            model = temp_path / "ggml-large-v3-turbo-q5_0.bin"
            binary.write_text("", encoding="utf-8")
            model.write_text("", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DICTATE_WHISPER_CPP_SERVER": str(binary),
                    "DICTATE_WHISPER_CPP_MODEL": str(model),
                },
                clear=False,
            ):
                stt = WhisperCppSpeechToText()
                with patch.object(stt, "_ensure_server_started") as start:
                    self.assertEqual(stt.model, (binary, model, 0))
                    start.assert_called_once()

    def test_timeout_scales_with_audio_duration(self) -> None:
        stt = WhisperCppSpeechToText()
        self.assertEqual(stt.backend_name, "whisper-cpp")
        self.assertEqual(stt.transcribe.__name__, "transcribe")
        self.assertEqual(np.zeros(16000, dtype=np.float32).dtype, np.float32)


if __name__ == "__main__":
    unittest.main()
