from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class RepoDefaultConfigTests(unittest.TestCase):
    def test_default_install_config_is_valid_and_turbo_seeded(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "default-config.yaml"
        data = yaml.safe_load(config_path.read_text())

        self.assertEqual(data["stt_backend"], "faster-whisper")
        self.assertEqual(data["stt_model"], "turbo")
        self.assertEqual(data["stt_device"], "auto")
        self.assertEqual(data["stt_compute_type"], "int8")
        self.assertIsInstance(data["hotwords"], list)
        self.assertGreater(len(data["hotwords"]), 0)
        self.assertTrue(all(isinstance(word, str) and word.strip() for word in data["hotwords"]))


if __name__ == "__main__":
    unittest.main()
