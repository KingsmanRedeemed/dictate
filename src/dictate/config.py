"""Load dictate config from ~/.config/dictate/config.yaml."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "dictate" / "config.yaml"


@dataclass(slots=True)
class Config:
    hotwords: list[str] = field(default_factory=list)

    @property
    def hotwords_str(self) -> str | None:
        """Hotwords as a single space-separated string for faster-whisper."""
        return " ".join(self.hotwords) if self.hotwords else None


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Load config from YAML file. Returns defaults if file doesn't exist."""
    if not path.is_file():
        return Config()

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        logger.warning(f"Failed to parse {path}, using defaults")
        return Config()

    hotwords = data.get("hotwords", [])
    if isinstance(hotwords, str):
        hotwords = [hotwords]

    return Config(hotwords=hotwords)


def _load_raw(path: Path = CONFIG_PATH) -> dict:
    """Load raw YAML dict, preserving all keys."""
    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def _save_raw(data: dict, path: Path = CONFIG_PATH) -> None:
    """Write dict back to YAML, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False))


def add_hotwords(words: list[str], path: Path = CONFIG_PATH) -> list[str]:
    """Add words to the hotwords list. Returns list of newly added words."""
    data = _load_raw(path)
    existing = data.get("hotwords", [])
    if isinstance(existing, str):
        existing = [existing]

    added = [w for w in words if w not in existing]
    if added:
        data["hotwords"] = existing + added
        _save_raw(data, path)
    return added


def remove_hotwords(words: list[str], path: Path = CONFIG_PATH) -> list[str]:
    """Remove words from the hotwords list. Returns list of actually removed words."""
    data = _load_raw(path)
    existing = data.get("hotwords", [])
    if isinstance(existing, str):
        existing = [existing]

    removed = [w for w in words if w in existing]
    if removed:
        data["hotwords"] = [w for w in existing if w not in words]
        _save_raw(data, path)
    return removed
