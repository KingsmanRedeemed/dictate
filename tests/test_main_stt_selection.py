from __future__ import annotations

import contextlib
import io
import unittest

from dictate import __main__ as main_module
from dictate.config import Config


class MainSttSelectionTests(unittest.TestCase):
    def test_saved_selection_used_when_cli_does_not_override(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args([])

        with contextlib.redirect_stderr(io.StringIO()):
            backend, model = main_module._resolve_startup_stt(
                args=args,
                cli_args=[],
                config=Config(stt_backend="nemo-canary", stt_model="nvidia/canary-1b-v2"),
            )

        self.assertEqual(backend, "nemo-canary")
        self.assertEqual(model, "nvidia/canary-1b-v2")

    def test_cli_flags_override_saved_selection(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args(["--stt-backend", "faster-whisper", "--model", "small"])

        with contextlib.redirect_stderr(io.StringIO()):
            backend, model = main_module._resolve_startup_stt(
                args=args,
                cli_args=["--stt-backend", "faster-whisper", "--model", "small"],
                config=Config(stt_backend="nemo-canary", stt_model="nvidia/canary-1b-v2"),
            )

        self.assertEqual(backend, "faster-whisper")
        self.assertEqual(model, "small")

    def test_invalid_saved_backend_falls_back_to_cli_defaults(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args([])

        with contextlib.redirect_stderr(io.StringIO()):
            backend, model = main_module._resolve_startup_stt(
                args=args,
                cli_args=[],
                config=Config(stt_backend="not-a-backend", stt_model="x"),
            )

        self.assertEqual(backend, "faster-whisper")
        self.assertEqual(model, "base")

    def test_saved_runtime_profile_used_when_cli_does_not_override(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args([])

        with contextlib.redirect_stderr(io.StringIO()):
            device, compute_type = main_module._resolve_startup_runtime(
                args=args,
                cli_args=[],
                config=Config(stt_device="cuda", stt_compute_type="float16"),
            )

        self.assertEqual(device, "cuda")
        self.assertEqual(compute_type, "float16")

    def test_cli_runtime_flags_override_saved_profile(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args(["--device", "cpu", "--compute-type", "float32"])

        with contextlib.redirect_stderr(io.StringIO()):
            device, compute_type = main_module._resolve_startup_runtime(
                args=args,
                cli_args=["--device", "cpu", "--compute-type", "float32"],
                config=Config(stt_device="cuda", stt_compute_type="float16"),
            )

        self.assertEqual(device, "cpu")
        self.assertEqual(compute_type, "float32")

    def test_invalid_saved_runtime_profile_falls_back_to_cli_defaults(self) -> None:
        parser = main_module.build_parser()
        args = parser.parse_args([])

        with contextlib.redirect_stderr(io.StringIO()):
            device, compute_type = main_module._resolve_startup_runtime(
                args=args,
                cli_args=[],
                config=Config(stt_device="bad-device", stt_compute_type="bad-compute"),
            )

        self.assertEqual(device, "auto")
        self.assertEqual(compute_type, "int8")


if __name__ == "__main__":
    unittest.main()
