from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dictate.model_state import (
    get_model_error,
    is_model_prepared,
    mark_model_failed,
    mark_model_prepared,
)


class ModelStateTests(unittest.TestCase):
    def test_mark_prepared_sets_ready_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "model-state.json"
            mark_model_prepared(
                backend="nemo-canary",
                model="nvidia/canary-1b-flash",
                device="auto",
                compute_type="int8",
                path=state_path,
            )
            self.assertTrue(
                is_model_prepared(
                    backend="nemo-canary",
                    model="nvidia/canary-1b-flash",
                    device="auto",
                    compute_type="int8",
                    path=state_path,
                )
            )

    def test_mark_failed_clears_ready_flag_and_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "model-state.json"
            mark_model_prepared(
                backend="nemo-canary",
                model="nvidia/canary-1b",
                device="cuda",
                compute_type="int8",
                path=state_path,
            )
            mark_model_failed(
                backend="nemo-canary",
                model="nvidia/canary-1b",
                device="cuda",
                compute_type="int8",
                error_message="download timeout",
                path=state_path,
            )
            self.assertFalse(
                is_model_prepared(
                    backend="nemo-canary",
                    model="nvidia/canary-1b",
                    device="cuda",
                    compute_type="int8",
                    path=state_path,
                )
            )
            self.assertEqual(
                get_model_error(
                    backend="nemo-canary",
                    model="nvidia/canary-1b",
                    device="cuda",
                    compute_type="int8",
                    path=state_path,
                ),
                "download timeout",
            )


if __name__ == "__main__":
    unittest.main()
