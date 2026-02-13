"""
dictate — local voice-to-text for the terminal.

Usage:
    dictate                   Push-to-talk daemon (hold Right Ctrl)
    dictate --once            One-shot: record until Enter, print to stdout
    dictate --once --copy     One-shot: record until Enter, copy to clipboard
    dictate --model small     Use a different whisper model
"""

import argparse
import subprocess
import sys
import threading

import numpy as np
import sounddevice as sd

from dictate.stt import SpeechToText

SAMPLE_RATE = 16000


def record_until_enter() -> np.ndarray:
    """Record from default mic until Enter is pressed."""
    chunks: list[np.ndarray] = []

    def callback(indata, frames, time, status):
        if status:
            print(f"  audio: {status}", file=sys.stderr)
        chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
    )

    print("Recording... (press Enter to stop)", file=sys.stderr)
    stream.start()
    input()
    stream.stop()
    stream.close()

    if not chunks:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(chunks).flatten()
    duration = len(audio) / SAMPLE_RATE
    print(f"  {duration:.1f}s captured", file=sys.stderr)
    return audio


def output_text(text: str, mode: str) -> None:
    """Send transcribed text to the chosen output."""
    if mode == "copy":
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        print("Copied to clipboard", file=sys.stderr)
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(description="Local voice-to-text for the terminal")
    parser.add_argument(
        "--once", action="store_true",
        help="One-shot mode: record until Enter, output text, exit",
    )
    parser.add_argument("--copy", action="store_true", help="One-shot: copy to clipboard (xclip)")
    parser.add_argument("--model", default="base", help="Whisper model size (default: base)")
    parser.add_argument("--device", default="auto", help="Compute device: cpu, cuda, auto")
    parser.add_argument(
        "--language", default=None,
        help="Language code (e.g. en). Auto-detect if omitted",
    )
    args = parser.parse_args()

    stt = SpeechToText(model_size=args.model, device=args.device)

    print(f"Loading model ({args.model})...", file=sys.stderr)
    _ = stt.model
    print("Ready.\n", file=sys.stderr)

    if args.once:
        _run_once(stt, args)
    else:
        _run_daemon(stt, args)


def _run_once(stt: SpeechToText, args):
    audio = record_until_enter()
    if len(audio) == 0:
        print("No audio captured", file=sys.stderr)
        sys.exit(1)

    text = stt.transcribe(audio, language=args.language)
    if not text.strip():
        print("No speech detected", file=sys.stderr)
        sys.exit(1)

    mode = "copy" if args.copy else "stdout"
    output_text(text.strip(), mode)


def _run_daemon(stt: SpeechToText, args):
    from dictate.daemon import Daemon
    Daemon(stt).run()


if __name__ == "__main__":
    main()
