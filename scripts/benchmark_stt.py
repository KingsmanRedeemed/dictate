#!/usr/bin/env python3
"""Compatibility wrapper around the package benchmark CLI."""

from __future__ import annotations

from dictate.benchmark import run_benchmark


if __name__ == "__main__":
    raise SystemExit(run_benchmark())
