from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dictate.config import add_hotwords, load_config, set_stt_selection


class ConfigSelectionTests(unittest.TestCase):
    def test_set_stt_selection_persists_backend_model_and_preserves_hotwords(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            add_hotwords(["OpenBao"], path=config_path)

            set_stt_selection(
                backend="nemo-canary",
                model="nvidia/canary-1b-flash",
                path=config_path,
            )

            config = load_config(path=config_path)
            self.assertEqual(config.hotwords, ["OpenBao"])
            self.assertEqual(config.stt_backend, "nemo-canary")
            self.assertEqual(config.stt_model, "nvidia/canary-1b-flash")


if __name__ == "__main__":
    unittest.main()
