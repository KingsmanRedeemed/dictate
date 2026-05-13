from __future__ import annotations

import unittest

from dictate.config import Config
from dictate.doctor import _resolve_doctor_runtime, build_parser


class DoctorConfigTests(unittest.TestCase):
    def test_saved_runtime_used_when_cli_does_not_override(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])

        runtime = _resolve_doctor_runtime(
            args=args,
            cli_args=[],
            config=Config(
                stt_backend="whisper-cpp",
                stt_model="large-v3-turbo-q5_0",
                stt_device="cpu",
                push_to_talk_combo="ctrl+space",
            ),
        )

        self.assertEqual(runtime.stt_backend, "whisper-cpp")
        self.assertEqual(runtime.model_name, "large-v3-turbo-q5_0")
        self.assertEqual(runtime.device, "cpu")
        self.assertEqual(runtime.push_to_talk_combo, "ctrl+space")
        self.assertEqual(runtime.warnings, [])

    def test_cli_flags_override_saved_runtime(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--stt-backend",
                "faster-whisper",
                "--model",
                "base",
                "--device",
                "auto",
                "--push-to-talk-combo",
                "ctrl_l",
            ]
        )

        runtime = _resolve_doctor_runtime(
            args=args,
            cli_args=[
                "--stt-backend",
                "faster-whisper",
                "--model",
                "base",
                "--device",
                "auto",
                "--push-to-talk-combo",
                "ctrl_l",
            ],
            config=Config(
                stt_backend="whisper-cpp",
                stt_model="large-v3-turbo-q5_0",
                stt_device="cpu",
                push_to_talk_combo="ctrl+space",
            ),
        )

        self.assertEqual(runtime.stt_backend, "faster-whisper")
        self.assertEqual(runtime.model_name, "base")
        self.assertEqual(runtime.device, "auto")
        self.assertEqual(runtime.push_to_talk_combo, "ctrl_l")


if __name__ == "__main__":
    unittest.main()
