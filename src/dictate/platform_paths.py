"""Platform-specific application paths."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_NAME = "dictate"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def user_config_dir() -> Path:
    if is_windows():
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def user_data_dir() -> Path:
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Local" / APP_NAME

    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def fallback_log_dir() -> Path:
    return Path(tempfile.gettempdir()) / "dictate-logs"
