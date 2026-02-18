"""
dictate — local voice-to-text for the terminal.

Usage:
    dictate                   Push-to-talk with system tray icon
    dictate --no-tray         Push-to-talk headless (no tray icon)
    dictate --once            One-shot: record until Enter, print to stdout
    dictate --once --copy     One-shot: record until Enter, copy to clipboard
    dictate --stt-backend nemo-canary --model nvidia/canary-1b-flash
    dictate --type-backend wtype  Force typing backend for daemon mode
    dictate --model large-v3-turbo  Use a different STT model
    dictate --add-hotword X   Save a hotword for improved recognition
    dictate --list-hotwords   List saved hotwords
"""

import argparse
import sys
import threading

from dictate.audio import AudioCaptureError, SoundDeviceRecorder
from dictate.config import add_hotwords, load_config, remove_hotwords
from dictate.engine import DictationEngine
from dictate.outputs import (
    BackendUnavailableError,
    ClipboardOutput,
    OutputError,
    StdoutOutput,
    resolve_typing_backend,
)
from dictate.preflight import run_preflight
from dictate.stt import (
    DEFAULT_MODELS,
    NEMO_CANARY_MODELS,
    SpeechToText,
    create_speech_to_text,
)

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
    parser.add_argument(
        "--stt-backend",
        choices=["faster-whisper", "nemo-canary"],
        default="faster-whisper",
        help="Speech-to-text backend (default: faster-whisper)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model name. "
            "faster-whisper examples: turbo, large-v3-turbo, large-v3. "
            f"nemo-canary examples: {', '.join(NEMO_CANARY_MODELS)}."
        ),
    )
    parser.add_argument("--device", default="auto", help="Compute device: cpu, cuda, auto")
    parser.add_argument(
        "--language", default=None,
        help="Language code (e.g. en). Auto-detect if omitted",
    )
    parser.add_argument(
        "--hotwords", default=None,
        help="Comma-separated words to boost recognition (e.g. 'OpenBao,Vikunja')",
    )
    parser.add_argument(
        "--add-hotword", metavar="WORD",
        help="Add word(s) to saved hotwords (comma-separated). Restart dictate to apply.",
    )
    parser.add_argument(
        "--remove-hotword", metavar="WORD",
        help="Remove word(s) from saved hotwords (comma-separated).",
    )
    parser.add_argument(
        "--list-hotwords", action="store_true",
        help="List saved hotwords and exit.",
    )
    args = parser.parse_args()

    # --- Hotword management (no model load, no preflight) ---
    if args.add_hotword:
        words = [w.strip() for w in args.add_hotword.split(",") if w.strip()]
        added = add_hotwords(words)
        if added:
            print(f"Added: {', '.join(added)}", file=sys.stderr)
            print("Restart dictate to apply.", file=sys.stderr)
        else:
            print("Already present, nothing to add.", file=sys.stderr)
        sys.exit(0)

    if args.remove_hotword:
        words = [w.strip() for w in args.remove_hotword.split(",") if w.strip()]
        removed = remove_hotwords(words)
        if removed:
            print(f"Removed: {', '.join(removed)}", file=sys.stderr)
            print("Restart dictate to apply.", file=sys.stderr)
        else:
            print("Not found, nothing to remove.", file=sys.stderr)
        sys.exit(0)

    if args.list_hotwords:
        config = load_config()
        if config.hotwords:
            for word in config.hotwords:
                print(word)
        else:
            print("No hotwords configured.", file=sys.stderr)
        sys.exit(0)

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

    model_name = args.model or DEFAULT_MODELS[args.stt_backend]
    stt = create_speech_to_text(
        backend=args.stt_backend,
        model=model_name,
        device=args.device,
    )

    print(
        f"Loading STT backend '{args.stt_backend}' model '{model_name}'...",
        file=sys.stderr,
    )
    try:
        _ = stt.model
    except Exception as exc:  # noqa: BLE001
        print(
            f"Failed to load backend '{args.stt_backend}' model '{model_name}': {exc}",
            file=sys.stderr,
        )
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
