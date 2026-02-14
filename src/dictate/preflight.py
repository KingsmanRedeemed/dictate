"""Environment checks for predictable runtime behavior."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import sounddevice as sd

from dictate.outputs import (
    BackendUnavailableError,
    command_exists,
    detect_session_type,
    resolve_typing_backend,
)


@dataclass(slots=True)
class PreflightReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_preflight(
    *,
    require_typing: bool,
    require_clipboard: bool,
    typing_backend: str = "auto",
) -> PreflightReport:
    report = PreflightReport()

    _check_microphone(report)
    _check_typing(report, require_typing=require_typing, typing_backend=typing_backend)
    _check_clipboard(report, require_clipboard=require_clipboard)
    return report


def _check_microphone(report: PreflightReport) -> None:
    result: dict[str, object] = {}

    def query_devices() -> None:
        try:
            result["devices"] = sd.query_devices()
            result["default"] = sd.default.device
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=query_devices, daemon=True)
    thread.start()
    thread.join(timeout=3.0)

    if thread.is_alive():
        report.warnings.append("Audio device probe timed out; skipping microphone preflight checks.")
        return

    error = result.get("error")
    if error is not None:
        report.errors.append(f"Could not query audio devices: {error}")
        return

    devices = result.get("devices")
    try:
        input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
    except Exception:  # noqa: BLE001
        report.warnings.append("Unable to inspect microphone devices.")
        return
    if not input_devices:
        report.errors.append("No microphone input devices detected.")

    default_pair = result.get("default")
    if isinstance(default_pair, (tuple, list)) and len(default_pair) >= 1:
        default_input = default_pair[0]
        if default_input is None or default_input < 0:
            report.warnings.append("No default input device configured.")
    else:
        report.warnings.append("Unable to determine the default input device.")


def _check_typing(report: PreflightReport, *, require_typing: bool, typing_backend: str) -> None:
    if not require_typing:
        return

    session = detect_session_type()
    report.notes.append(f"Session type: {session}")

    try:
        backend = resolve_typing_backend(preferred=typing_backend)
    except BackendUnavailableError as exc:
        report.errors.append(str(exc))
        return

    report.notes.append(f"Typing backend: {backend.name}")


def _check_clipboard(report: PreflightReport, *, require_clipboard: bool) -> None:
    if not require_clipboard:
        return
    if not command_exists("xclip"):
        report.errors.append("xclip is not installed (required for --copy).")
