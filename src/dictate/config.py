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
    stt_backend: str | None = None
    stt_model: str | None = None
    stt_device: str | None = None
    stt_compute_type: str | None = None

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

    stt_backend = data.get("stt_backend")
    stt_model = data.get("stt_model")
    stt_device = data.get("stt_device")
    stt_compute_type = data.get("stt_compute_type")
    if not isinstance(stt_backend, str):
        stt_backend = None
    if not isinstance(stt_model, str):
        stt_model = None
    if not isinstance(stt_device, str):
        stt_device = None
    if not isinstance(stt_compute_type, str):
        stt_compute_type = None

    return Config(
        hotwords=hotwords,
        stt_backend=stt_backend,
        stt_model=stt_model,
        stt_device=stt_device,
        stt_compute_type=stt_compute_type,
    )


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


def set_stt_selection(backend: str, model: str, path: Path = CONFIG_PATH) -> None:
    """Persist selected STT backend/model for tray startup defaults."""
    data = _load_raw(path)
    data["stt_backend"] = backend
    data["stt_model"] = model
    _save_raw(data, path)


def set_stt_runtime_profile(device: str, compute_type: str, path: Path = CONFIG_PATH) -> None:
    """Persist selected STT runtime profile for tray startup defaults."""
    data = _load_raw(path)
    data["stt_device"] = device
    data["stt_compute_type"] = compute_type
    _save_raw(data, path)
