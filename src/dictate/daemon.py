"""Push-to-talk daemon. Listens for Right Ctrl and runs shared dictation pipeline."""

from __future__ import annotations

import queue
import sys
import threading

import numpy as np
from pynput import keyboard

from dictate.audio import AudioCaptureError, SoundDeviceRecorder
from dictate.engine import DictationEngine, TranscriptionResult
from dictate.lexicon import LexiconMode
from dictate.outputs import TextOutput
from dictate.stt import SpeechToText

SAMPLE_RATE = 16000


class Daemon:
    def __init__(
        self,
        stt: SpeechToText,
        *,
        output: TextOutput,
        language: str | None = None,
        hotwords: str | None = None,
        lexicon_mode: LexiconMode = "native",
        lexicon_replacements: dict[str, str] | None = None,
    ):
        self.active = True
        self.language = language
        self.output = output
        self.engine = DictationEngine(
            stt=stt,
            sample_rate=SAMPLE_RATE,
            hotwords=hotwords,
            lexicon_mode=lexicon_mode,
            lexicon_replacements=lexicon_replacements,
        )
        self.recorder = SoundDeviceRecorder(sample_rate=SAMPLE_RATE)
        self._engine_lock = threading.Lock()

        self._stop = threading.Event()
        self._listener: keyboard.Listener | None = None
        self._worker: threading.Thread | None = None
        self._audio_queue: queue.Queue[np.ndarray | None] = queue.Queue()

    def pause(self) -> None:
        """Stop listening for hotkey."""
        self.active = False
        if self.recorder.is_recording:
            self._finalize_recording()

    def resume(self) -> None:
        """Resume listening for hotkey."""
        self.active = True

    def set_hotwords(self, hotwords: str | None) -> None:
        """Update hotwords without restarting daemon."""
        with self._engine_lock:
            self.engine.set_hotwords(hotwords)

    def switch_speech_to_text(self, stt: SpeechToText, *, hotwords: str | None = None) -> None:
        """Swap STT backend/model at runtime."""
        previous_stt: SpeechToText | None = None
        with self._engine_lock:
            previous_stt = self.engine.stt
            self.engine.stt = stt
            self.engine.set_hotwords(hotwords)
        if previous_stt is not None and previous_stt is not stt:
            try:
                previous_stt.release()
            except Exception as exc:  # noqa: BLE001
                print(f"Failed to release previous STT resources: {exc}", file=sys.stderr)

    def current_backend_model(self) -> tuple[str, str]:
        """Return active backend/model selection."""
        with self._engine_lock:
            return (self.engine.stt.backend_name, self.engine.stt.model_name)

    def runtime_stt_options(self) -> tuple[str, str]:
        """Return current STT device/compute options for new model instantiation."""
        with self._engine_lock:
            stt = self.engine.stt
            device = getattr(stt, "device", "auto")
            compute_type = getattr(stt, "compute_type", "int8")
            return (device, compute_type)

    def shutdown(self) -> None:
        """Clean shutdown."""
        if self._stop.is_set():
            return

        self._stop.set()

        if self.recorder.is_recording:
            self._finalize_recording()

        if self._listener:
            self._listener.stop()

        with self._engine_lock:
            try:
                self.engine.stt.release()
            except Exception:  # noqa: BLE001
                pass

        self._audio_queue.put(None)

    def _start_recording(self) -> None:
        if self.recorder.is_recording or not self.active:
            return

        try:
            self.recorder.start()
        except AudioCaptureError as exc:
            print(f"\r  Microphone error: {exc}", file=sys.stderr)
            return

        print("\r  \033[91m● Recording...\033[0m", end="", file=sys.stderr, flush=True)

    def _finalize_recording(self) -> None:
        try:
            audio = self.recorder.stop()
        except AudioCaptureError as exc:
            print(f"\r  Microphone error: {exc}", file=sys.stderr)
            return

        if audio.size > 0:
            self._audio_queue.put(audio)

    def _on_press(self, key) -> None:  # noqa: ANN001
        if key == keyboard.Key.ctrl_r and self.active:
            self._start_recording()

    def _on_release(self, key) -> None:  # noqa: ANN001
        if key == keyboard.Key.ctrl_r:
            self._finalize_recording()

    def start(self) -> None:
        """Start daemon threads (non-blocking). Returns immediately."""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

        self._worker = threading.Thread(target=self._transcription_loop, daemon=True)
        self._worker.start()

    def run(self) -> None:
        """Start daemon and block (for headless mode)."""
        print("dictate daemon running", file=sys.stderr)
        print(f"  Hold Right Ctrl to dictate, release to transcribe ({self.output.name})", file=sys.stderr)
        print("  Ctrl+C to quit\n", file=sys.stderr)

        self.start()

        try:
            self._stop.wait()
        except KeyboardInterrupt:
            print("\nStopping...", file=sys.stderr)
        finally:
            self.shutdown()

    def _transcription_loop(self) -> None:
        while not self._stop.is_set():
            audio = self._audio_queue.get()
            if audio is None:
                break

            duration = len(audio) / SAMPLE_RATE
            print(
                f"\r  Transcribing {duration:.1f}s...   ",
                end="",
                file=sys.stderr,
                flush=True,
            )
            with self._engine_lock:
                result = self.engine.transcribe(audio, language=self.language)
            self._handle_result(result)

    def _handle_result(self, result: TranscriptionResult) -> None:
        if result.status == "empty":
            print("\r  No audio captured", file=sys.stderr)
            return

        if result.status == "too_short":
            print("\r  Too short, skipped", file=sys.stderr)
            return

        if result.status == "no_speech":
            print("\r  No speech detected", file=sys.stderr)
            return

        if result.status == "error":
            message = result.error or "unknown transcription error"
            print(f"\r  Transcription failed: {message}", file=sys.stderr)
            return

        try:
            self.output.send(result.text)
        except Exception as exc:  # noqa: BLE001
            print(f"\r  Output backend failed ({self.output.name}): {exc}", file=sys.stderr)
            return

        print(f"\r  Typed: {result.text}", file=sys.stderr)
