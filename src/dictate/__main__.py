"""
dictate — local voice-to-text for the terminal.

Usage:
    dictate              Print transcription to stdout
    dictate --type       Type into focused window (xdotool)
    dictate --copy       Copy to clipboard (xclip)
    dictate --model small  Use a different whisper model
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
    stop = threading.Event()

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
    stop.set()
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
    if mode == "type":
        subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=True)
    elif mode == "copy":
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        print("Copied to clipboard", file=sys.stderr)
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(description="Local voice-to-text for the terminal")
    parser.add_argument("--type", action="store_true", help="Type into focused window (xdotool)")
    parser.add_argument("--copy", action="store_true", help="Copy to clipboard (xclip)")
    parser.add_argument("--model", default="base", help="Whisper model size (default: base)")
    parser.add_argument("--device", default="auto", help="Compute device: cpu, cuda, auto")
    parser.add_argument("--language", default=None, help="Language code (e.g. en). Auto-detect if omitted")
    args = parser.parse_args()

    mode = "type" if args.type else "copy" if args.copy else "stdout"

    stt = SpeechToText(model_size=args.model, device=args.device)

    # Warm up model before recording
    print(f"Loading model ({args.model})...", file=sys.stderr)
    _ = stt.model
    print("Ready.", file=sys.stderr)

    audio = record_until_enter()

    if len(audio) == 0:
        print("No audio captured", file=sys.stderr)
        sys.exit(1)

    text = stt.transcribe(audio, language=args.language)

    if not text.strip():
        print("No speech detected", file=sys.stderr)
        sys.exit(1)

    output_text(text.strip(), mode)


if __name__ == "__main__":
    main()
