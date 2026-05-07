from __future__ import annotations

import subprocess
import sys
import unittest

from dictate.version import PACKAGE_VERSION, RELEASE_VERSION


class VersionTests(unittest.TestCase):
    def test_release_and_package_versions_are_calver(self) -> None:
        self.assertEqual(RELEASE_VERSION, "2026.5.7-1")
        self.assertEqual(PACKAGE_VERSION, "2026.5.7.post1")

    def test_calver_script_generates_release_and_pep440_versions(self) -> None:
        release = subprocess.check_output(
            [
                sys.executable,
                "scripts/calver.py",
                "--date",
                "2026-05-07",
                "--sequence",
                "1",
            ],
            text=True,
        ).strip()
        pep440 = subprocess.check_output(
            [
                sys.executable,
                "scripts/calver.py",
                "--date",
                "2026-05-07",
                "--sequence",
                "1",
                "--format",
                "pep440",
            ],
            text=True,
        ).strip()

        self.assertEqual(release, RELEASE_VERSION)
        self.assertEqual(pep440, PACKAGE_VERSION)


if __name__ == "__main__":
    unittest.main()
