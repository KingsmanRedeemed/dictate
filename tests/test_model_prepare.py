from __future__ import annotations

import unittest

from dictate.model_prepare import _should_retry_on_cpu


class ModelPrepareTests(unittest.TestCase):
    def test_retry_on_cpu_when_cuda_busy_for_auto(self) -> None:
        exc = RuntimeError("CUDA failed with error CUDA-capable device(s) is/are busy or unavailable")
        self.assertTrue(_should_retry_on_cpu(exc, requested_device="auto"))

    def test_retry_on_cpu_when_cuda_oom_for_cuda_device(self) -> None:
        exc = RuntimeError("CUDA failed with error out of memory")
        self.assertTrue(_should_retry_on_cpu(exc, requested_device="cuda"))

    def test_no_retry_on_cpu_for_non_cuda_devices(self) -> None:
        exc = RuntimeError("CUDA failed with error CUDA-capable device(s) is/are busy or unavailable")
        self.assertFalse(_should_retry_on_cpu(exc, requested_device="cpu"))


if __name__ == "__main__":
    unittest.main()
