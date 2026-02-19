from __future__ import annotations

import unittest
from unittest.mock import patch

from dictate import __main__ as main_module


class MainBenchmarkDispatchTests(unittest.TestCase):
    def test_benchmark_subcommand_dispatches_to_benchmark_runner(self) -> None:
        with patch("dictate.__main__.run_benchmark", return_value=7) as run_benchmark:
            result = main_module.main(["benchmark", "--manifest", "benchmarks/example_manifest.csv"])

        self.assertEqual(result, 7)
        run_benchmark.assert_called_once_with(["--manifest", "benchmarks/example_manifest.csv"])

    def test_doctor_subcommand_dispatches_to_doctor_runner(self) -> None:
        with patch("dictate.__main__.run_doctor", return_value=3) as run_doctor:
            result = main_module.main(["doctor", "--quick"])

        self.assertEqual(result, 3)
        run_doctor.assert_called_once_with(["--quick"])


if __name__ == "__main__":
    unittest.main()
