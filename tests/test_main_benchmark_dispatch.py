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


if __name__ == "__main__":
    unittest.main()
