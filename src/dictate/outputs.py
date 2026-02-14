"""Text output adapters and typing backend selection."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol


class OutputError(RuntimeError):
    """Raised when a text output backend fails."""


class BackendUnavailableError(RuntimeError):
    """Raised when no suitable typing backend is available."""


class TextOutput(Protocol):
    name: str

    def send(self, text: str) -> None:
        """Emit text through this output backend."""


def detect_session_type() -> str:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type in {"x11", "wayland"}:
        return session_type
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


@dataclass(slots=True)
class StdoutOutput:
    name: str = "stdout"

    def send(self, text: str) -> None:
        print(text)


@dataclass(slots=True)
class ClipboardOutput:
    name: str = "clipboard"

    def send(self, text: str) -> None:
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=True,
            )
        except FileNotFoundError as exc:
            raise OutputError("xclip is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise OutputError(f"clipboard command failed: {exc}") from exc


@dataclass(slots=True)
class XdotoolOutput:
    name: str = "xdotool"

    def send(self, text: str) -> None:
        try:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--delay", "0", text],
                check=True,
            )
        except FileNotFoundError as exc:
            raise OutputError("xdotool is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise OutputError(f"xdotool failed: {exc}") from exc


@dataclass(slots=True)
class WtypeOutput:
    name: str = "wtype"

    def send(self, text: str) -> None:
        try:
            subprocess.run(["wtype", "--", text], check=True)
        except FileNotFoundError as exc:
            raise OutputError("wtype is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise OutputError(f"wtype failed: {exc}") from exc


@dataclass(slots=True)
class YdotoolOutput:
    name: str = "ydotool"

    def send(self, text: str) -> None:
        try:
            subprocess.run(["ydotool", "type", "--key-delay", "0", text], check=True)
        except FileNotFoundError as exc:
            raise OutputError("ydotool is not installed") from exc
        except subprocess.CalledProcessError as exc:
            raise OutputError(f"ydotool failed: {exc}") from exc


def available_typing_backends() -> list[str]:
    backends: list[str] = []
    for backend in ("xdotool", "wtype", "ydotool"):
        if command_exists(backend):
            backends.append(backend)
    return backends


def _build_typing_output(backend: str) -> TextOutput:
    if backend == "xdotool":
        return XdotoolOutput()
    if backend == "wtype":
        return WtypeOutput()
    if backend == "ydotool":
        return YdotoolOutput()
    raise BackendUnavailableError(f"unknown typing backend: {backend}")


def resolve_typing_backend(preferred: str = "auto") -> TextOutput:
    """Pick a typing backend based on session type and availability."""
    if preferred != "auto":
        if not command_exists(preferred):
            raise BackendUnavailableError(
                f"requested typing backend '{preferred}' is not installed"
            )
        return _build_typing_output(preferred)

    session = detect_session_type()
    if session == "wayland":
        candidates = ["wtype", "ydotool", "xdotool"]
    elif session == "x11":
        candidates = ["xdotool", "wtype", "ydotool"]
    else:
        candidates = ["xdotool", "wtype", "ydotool"]

    for candidate in candidates:
        if command_exists(candidate):
            return _build_typing_output(candidate)

    raise BackendUnavailableError(
        "no typing backend found; install one of: xdotool, wtype, ydotool"
    )
