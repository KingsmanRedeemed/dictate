"""Push-to-talk daemon. Holds model in memory, listens for Right Ctrl."""

import subprocess
import sys
import threading

import numpy as np
import sounddevice as sd
from pynput import keyboard

from dictate.stt import SpeechToText

SAMPLE_RATE = 16000


class Daemon:
    def __init__(self, stt: SpeechToText):
        self.stt = stt
        self.recording = False
        self.chunks: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self._transcribe = threading.Event()
        self._lock = threading.Lock()

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"  audio: {status}", file=sys.stderr)
        with self._lock:
            self.chunks.append(indata.copy())

    def _start_recording(self):
        if self.recording:
            return
        self.recording = True
        self.chunks = []
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        self.stream.start()
        print("\r  \033[91m● Recording...\033[0m", end="", file=sys.stderr, flush=True)

    def _stop_recording(self):
        if not self.recording:
            return
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self._transcribe.set()

    def _on_press(self, key):
        if key == keyboard.Key.ctrl_r:
            self._start_recording()

    def _on_release(self, key):
        if key == keyboard.Key.ctrl_r:
            self._stop_recording()

    def run(self):
        print("dictate daemon running", file=sys.stderr)
        print("  Hold Right Ctrl to dictate, release to transcribe", file=sys.stderr)
        print("  Ctrl+C to quit\n", file=sys.stderr)

        listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        listener.start()

        try:
            while True:
                self._transcribe.wait()
                self._transcribe.clear()

                with self._lock:
                    if not self.chunks:
                        continue
                    audio = np.concatenate(self.chunks).flatten()
                    self.chunks = []

                duration = len(audio) / SAMPLE_RATE
                if duration < 0.3:
                    print("\r  Too short, skipped", file=sys.stderr)
                    continue

                print(
                    f"\r  Transcribing {duration:.1f}s...   ",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
                text = self.stt.transcribe(audio)

                if text.strip():
                    subprocess.run(
                        ["xdotool", "type", "--clearmodifiers", "--delay", "0", text.strip()],
                        check=True,
                    )
                    print(f"\r  Typed: {text.strip()}", file=sys.stderr)
                else:
                    print("\r  No speech detected", file=sys.stderr)
        except KeyboardInterrupt:
            print("\nStopping...", file=sys.stderr)
        finally:
            listener.stop()
