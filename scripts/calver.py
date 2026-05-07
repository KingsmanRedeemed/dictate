#!/usr/bin/env python3
"""Generate Dictate CalVer release versions."""

from __future__ import annotations

import argparse
from datetime import date


def release_version(day: date, sequence: int) -> str:
    return f"{day.year}.{day.month}.{day.day}-{sequence}"


def pep440_version(day: date, sequence: int) -> str:
    return f"{day.year}.{day.month}.{day.day}.post{sequence}"


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Dictate CalVer versions")
    parser.add_argument("--date", type=_parse_date, default=date.today())
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument(
        "--format",
        choices=["release", "pep440"],
        default="release",
        help="release prints YYYY.M.D-N; pep440 prints YYYY.M.D.postN",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.sequence < 1:
        raise SystemExit("--sequence must be >= 1")
    if args.format == "pep440":
        print(pep440_version(args.date, args.sequence))
    else:
        print(release_version(args.date, args.sequence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
