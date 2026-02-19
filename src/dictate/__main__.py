"""
dictate — local voice-to-text for the terminal.

Usage:
    dictate                   Push-to-talk with system tray icon
    dictate --no-tray         Push-to-talk headless (no tray icon)
    dictate --once            One-shot: record until Enter, print to stdout
    dictate --once --copy     One-shot: record until Enter, copy to clipboard
    dictate benchmark ...     Benchmark STT backends on local WAV files
    dictate --stt-backend nemo-canary --model nvidia/canary-1b-flash
    dictate --type-backend wtype  Force typing backend for daemon mode
    dictate --model large-v3-turbo  Use a different STT model
    dictate --add-hotword X   Save a hotword for improved recognition
    dictate --list-hotwords   List saved hotwords
"""

import argparse
import sys
import threading
from typing import Sequence

from dictate.audio import AudioCaptureError, SoundDeviceRecorder
from dictate.benchmark import run_benchmark
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
    ComputeDevice,
    NEMO_CANARY_MODELS,
    STT_BACKENDS,
    SpeechToText,
    SttBackend,
    create_speech_to_text,
    resolve_model_name,
)

SAMPLE_RATE = 16000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local voice-to-text for the terminal",
        epilog="For STT benchmarking use: dictate benchmark --help",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="One-shot mode: record until Enter, output text, exit",
    )
    parser.add_argument("--copy", action="store_true", help="One-shot: copy to clipboard (xclip)")
    parser.add_argument(
        "--no-tray",
        action="store_true",
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
        choices=STT_BACKENDS,
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
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "auto"],
        default="auto",
        help="Compute device: cpu, cuda, auto",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language code (e.g. en). Auto-detect if omitted",
    )
    parser.add_argument(
        "--hotwords",
        default=None,
        help="Comma-separated words to boost recognition (e.g. 'OpenBao,Vikunja')",
    )
    parser.add_argument(
        "--add-hotword",
        metavar="WORD",
        help="Add word(s) to saved hotwords (comma-separated). Restart dictate to apply.",
    )
    parser.add_argument(
        "--remove-hotword",
        metavar="WORD",
        help="Remove word(s) from saved hotwords (comma-separated).",
    )
    parser.add_argument(
        "--list-hotwords",
        action="store_true",
        help="List saved hotwords and exit.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    cli_args = list(argv) if argv is not None else sys.argv[1:]
    if cli_args and cli_args[0] == "benchmark":
        return run_benchmark(cli_args[1:])

    parser = build_parser()
    args = parser.parse_args(cli_args)

    handled = _handle_hotword_commands(args)
    if handled is not None:
        return handled

    stt_backend = args.stt_backend
    model_name = resolve_model_name(stt_backend, args.model)

    _run_preflight_or_exit(
        require_typing=not args.once,
        require_clipboard=args.once and args.copy,
        typing_backend=args.type_backend,
        stt_backend=stt_backend,
        stt_model=model_name,
        stt_device=args.device,
    )

    stt = _load_stt_or_exit(
        stt_backend=stt_backend,
        model_name=model_name,
        device=args.device,
    )
    language = _resolve_language(stt, args.language)
    hotwords = _resolve_hotwords(stt, cli_hotwords=args.hotwords)

    if args.once:
        _run_once(stt, copy_to_clipboard=args.copy, language=language, hotwords=hotwords)
        return 0
    if args.no_tray:
        _run_headless(
            stt,
            type_backend=args.type_backend,
            language=language,
            hotwords=hotwords,
        )
        return 0
    _run_tray(
        stt,
        type_backend=args.type_backend,
        language=language,
        hotwords=hotwords,
    )
    return 0


def _run_preflight_or_exit(
    *,
    require_typing: bool,
    require_clipboard: bool,
    typing_backend: str,
    stt_backend: SttBackend,
    stt_model: str,
    stt_device: ComputeDevice,
) -> None:
    report = run_preflight(
        require_typing=require_typing,
        require_clipboard=require_clipboard,
        typing_backend=typing_backend,
        stt_backend=stt_backend,
        stt_model=stt_model,
        stt_device=stt_device,
    )
    for note in report.notes:
        print(f"Preflight: {note}", file=sys.stderr)
    for warning in report.warnings:
        print(f"Preflight warning: {warning}", file=sys.stderr)
    if report.errors:
        for error in report.errors:
            print(f"Preflight error: {error}", file=sys.stderr)
        raise SystemExit(2)


def _load_stt_or_exit(
    *,
    stt_backend: SttBackend,
    model_name: str,
    device: ComputeDevice,
) -> SpeechToText:
    stt = create_speech_to_text(
        backend=stt_backend,
        model=model_name,
        device=device,
    )
    print(
        f"Loading STT backend '{stt_backend}' model '{model_name}'...",
        file=sys.stderr,
    )
    try:
        _ = stt.model
    except Exception as exc:  # noqa: BLE001
        print(
            f"Failed to load backend '{stt_backend}' model '{model_name}': {exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    print("Ready.\n", file=sys.stderr)
    return stt


def _resolve_language(stt: SpeechToText, language: str | None) -> str | None:
    if language and not stt.capabilities.supports_language_hint:
        print(
            f"Warning: backend '{stt.backend_name}' ignores --language; auto mode will be used.",
            file=sys.stderr,
        )
        return None
    return language


def _resolve_hotwords(stt: SpeechToText, *, cli_hotwords: str | None) -> str | None:
    config = load_config()
    words = list(config.hotwords)
    if cli_hotwords:
        words.extend(_parse_csv_words(cli_hotwords))
    hotwords_str = " ".join(words) if words else None
    if not hotwords_str:
        return None
    if not stt.capabilities.supports_hotwords:
        print(
            f"Warning: backend '{stt.backend_name}' does not support hotwords; ignoring configured hotwords.",
            file=sys.stderr,
        )
        return None
    print(f"Hotwords: {hotwords_str}", file=sys.stderr)
    return hotwords_str


def _parse_csv_words(value: str) -> list[str]:
    return [word.strip() for word in value.split(",") if word.strip()]


def _handle_hotword_commands(args) -> int | None:  # noqa: ANN001
    if args.add_hotword:
        added = add_hotwords(_parse_csv_words(args.add_hotword))
        if added:
            print(f"Added: {', '.join(added)}", file=sys.stderr)
            print("Restart dictate to apply.", file=sys.stderr)
        else:
            print("Already present, nothing to add.", file=sys.stderr)
        return 0

    if args.remove_hotword:
        removed = remove_hotwords(_parse_csv_words(args.remove_hotword))
        if removed:
            print(f"Removed: {', '.join(removed)}", file=sys.stderr)
            print("Restart dictate to apply.", file=sys.stderr)
        else:
            print("Not found, nothing to remove.", file=sys.stderr)
        return 0

    if args.list_hotwords:
        config = load_config()
        if config.hotwords:
            for word in config.hotwords:
                print(word)
        else:
            print("No hotwords configured.", file=sys.stderr)
        return 0
    return None


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


def _run_once(
    stt: SpeechToText,
    *,
    copy_to_clipboard: bool,
    language: str | None,
    hotwords: str | None,
) -> None:
    recorder = SoundDeviceRecorder(sample_rate=SAMPLE_RATE)
    engine = DictationEngine(stt=stt, sample_rate=SAMPLE_RATE, hotwords=hotwords)

    try:
        audio = record_until_enter(recorder)
    except AudioCaptureError as exc:
        print(f"Microphone error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    result = engine.transcribe(audio, language=language)
    if result.status == "empty":
        print("No audio captured", file=sys.stderr)
        raise SystemExit(1)
    if result.status == "too_short":
        print("Too short, skipped", file=sys.stderr)
        raise SystemExit(1)
    if result.status == "no_speech":
        print("No speech detected", file=sys.stderr)
        raise SystemExit(1)
    if result.status == "error":
        print(f"Transcription failed: {result.error}", file=sys.stderr)
        raise SystemExit(1)

    output = ClipboardOutput() if copy_to_clipboard else StdoutOutput()
    try:
        output.send(result.text)
    except OutputError as exc:
        print(f"Output error ({output.name}): {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if copy_to_clipboard:
        print("Copied to clipboard", file=sys.stderr)


def _resolve_typing_output_or_exit(type_backend: str):
    try:
        return resolve_typing_backend(type_backend)
    except BackendUnavailableError as exc:
        print(f"Typing backend error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def _run_headless(
    stt: SpeechToText,
    *,
    type_backend: str,
    language: str | None,
    hotwords: str | None,
) -> None:
    from dictate.daemon import Daemon

    output = _resolve_typing_output_or_exit(type_backend)
    Daemon(stt, output=output, language=language, hotwords=hotwords).run()


def _run_tray(
    stt: SpeechToText,
    *,
    type_backend: str,
    language: str | None,
    hotwords: str | None,
) -> None:
    from dictate.daemon import Daemon
    from dictate.tray import TrayIcon

    output = _resolve_typing_output_or_exit(type_backend)
    TrayIcon(Daemon(stt, output=output, language=language, hotwords=hotwords)).run()


if __name__ == "__main__":
    raise SystemExit(main())
