"""
dictate — local voice-to-text for the terminal.

Usage:
    dictate                   Push-to-talk with system tray icon
    dictate --no-tray         Push-to-talk headless (no tray icon)
    dictate --once            One-shot: record until Enter, print to stdout
    dictate --once --copy     One-shot: record until Enter, copy to clipboard
    dictate --type-backend wtype  Force typing backend for daemon mode
    dictate --model small     Use a different whisper model
"""

import argparse
import sys
import threading

from dictate.audio import AudioCaptureError, SoundDeviceRecorder
from dictate.config import load_config
from dictate.engine import DictationEngine
from dictate.outputs import (
    BackendUnavailableError,
    ClipboardOutput,
    OutputError,
    StdoutOutput,
    resolve_typing_backend,
)
from dictate.preflight import run_preflight
from dictate.stt import SpeechToText

SAMPLE_RATE = 16000


def record_until_enter(recorder: SoundDeviceRecorder):
    """Record from default mic until Enter is pressed."""
    stop = threading.Event()

    def wait_for_enter():
        try:
            input()
        except EOFError:
            pass
        stop.set()

    threading.Thread(target=wait_for_enter, daemon=True).start()

    print("Recording... (press Enter to stop)", file=sys.stderr)
    audio = recorder.record_until(stop.is_set)
    duration = len(audio) / SAMPLE_RATE
    print(f"  {duration:.1f}s captured", file=sys.stderr)
    return audio


def main():
    parser = argparse.ArgumentParser(description="Local voice-to-text for the terminal")
    parser.add_argument(
        "--once", action="store_true",
        help="One-shot mode: record until Enter, output text, exit",
    )
    parser.add_argument("--copy", action="store_true", help="One-shot: copy to clipboard (xclip)")
    parser.add_argument(
        "--no-tray", action="store_true",
        help="Headless daemon mode (no system tray icon)",
    )
    parser.add_argument(
        "--type-backend",
        choices=["auto", "xdotool", "wtype", "ydotool"],
        default="auto",
        help="Typing backend for daemon mode (default: auto)",
    )
    parser.add_argument("--model", default="base", help="Whisper model size (default: base)")
    parser.add_argument("--device", default="auto", help="Compute device: cpu, cuda, auto")
    parser.add_argument(
        "--language", default=None,
        help="Language code (e.g. en). Auto-detect if omitted",
    )
    parser.add_argument(
        "--hotwords", default=None,
        help="Comma-separated words to boost recognition (e.g. 'OpenBao,Vikunja')",
    )
    args = parser.parse_args()

    report = run_preflight(
        require_typing=not args.once,
        require_clipboard=args.once and args.copy,
        typing_backend=args.type_backend,
    )
    for note in report.notes:
        print(f"Preflight: {note}", file=sys.stderr)
    for warning in report.warnings:
        print(f"Preflight warning: {warning}", file=sys.stderr)
    if report.errors:
        for error in report.errors:
            print(f"Preflight error: {error}", file=sys.stderr)
        sys.exit(2)

    config = load_config()

    # Merge CLI hotwords with config file hotwords
    cli_hotwords = [w.strip() for w in args.hotwords.split(",") if w.strip()] if args.hotwords else []
    all_hotwords = config.hotwords + cli_hotwords
    hotwords_str = " ".join(all_hotwords) if all_hotwords else None

    if hotwords_str:
        print(f"Hotwords: {hotwords_str}", file=sys.stderr)

    stt = SpeechToText(model_size=args.model, device=args.device)

    print(f"Loading model ({args.model})...", file=sys.stderr)
    try:
        _ = stt.model
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load model '{args.model}': {exc}", file=sys.stderr)
        sys.exit(2)
    print("Ready.\n", file=sys.stderr)

    if args.once:
        _run_once(stt, args, hotwords=hotwords_str)
    elif args.no_tray:
        _run_headless(stt, args, hotwords=hotwords_str)
    else:
        _run_tray(stt, args, hotwords=hotwords_str)


def _run_once(stt: SpeechToText, args, *, hotwords: str | None = None):
    recorder = SoundDeviceRecorder(sample_rate=SAMPLE_RATE)
    engine = DictationEngine(stt=stt, sample_rate=SAMPLE_RATE, hotwords=hotwords)

    try:
        audio = record_until_enter(recorder)
    except AudioCaptureError as exc:
        print(f"Microphone error: {exc}", file=sys.stderr)
        sys.exit(1)

    result = engine.transcribe(audio, language=args.language)
    if result.status == "empty":
        print("No audio captured", file=sys.stderr)
        sys.exit(1)
    if result.status == "too_short":
        print("Too short, skipped", file=sys.stderr)
        sys.exit(1)
    if result.status == "no_speech":
        print("No speech detected", file=sys.stderr)
        sys.exit(1)
    if result.status == "error":
        print(f"Transcription failed: {result.error}", file=sys.stderr)
        sys.exit(1)

    output = ClipboardOutput() if args.copy else StdoutOutput()
    try:
        output.send(result.text)
    except OutputError as exc:
        print(f"Output error ({output.name}): {exc}", file=sys.stderr)
        sys.exit(1)

    if args.copy:
        print("Copied to clipboard", file=sys.stderr)


def _run_headless(stt: SpeechToText, args, *, hotwords: str | None = None):
    from dictate.daemon import Daemon

    try:
        output = resolve_typing_backend(args.type_backend)
    except BackendUnavailableError as exc:
        print(f"Typing backend error: {exc}", file=sys.stderr)
        sys.exit(2)
    Daemon(stt, output=output, language=args.language, hotwords=hotwords).run()


def _run_tray(stt: SpeechToText, args, *, hotwords: str | None = None):
    from dictate.daemon import Daemon
    from dictate.tray import TrayIcon

    try:
        output = resolve_typing_backend(args.type_backend)
    except BackendUnavailableError as exc:
        print(f"Typing backend error: {exc}", file=sys.stderr)
        sys.exit(2)
    TrayIcon(Daemon(stt, output=output, language=args.language, hotwords=hotwords)).run()


if __name__ == "__main__":
    main()
