# dictate

Local voice-to-text for Linux: hold `Right Ctrl`, speak, release to transcribe and type into the focused window.

This is intended to be an always-available desktop utility (tray icon) and a CLI-friendly one-shot recorder.

## Features

- Local speech-to-text with selectable backends:
  - `faster-whisper` (default)
  - `nemo-canary` (`nvidia/canary-1b`, `nvidia/canary-1b-flash`, `nvidia/canary-1b-v2`)
- Capability-aware backend contract (`hotwords`, language hint handling) so unsupported options fail soft with clear warnings.
- Push-to-talk daemon: `Right Ctrl` hold/release to record/transcribe/type.
- System tray toggle (pause/resume dictation).
- Tray menu STT switcher (change backend/model without restart).
- One-shot mode for terminal workflows (print to stdout or copy to clipboard).
- Typing backend auto-selection (`xdotool` on X11, `wtype`/`ydotool` on Wayland if installed).

## Requirements

- Linux (X11 recommended; Wayland supported depending on typing backend and hotkey support).
- Python >= 3.11.
- Microphone/audio: `sounddevice` + a working PortAudio setup.
- Typing backend (for daemon modes):
  - X11: `xdotool` (recommended)
  - Wayland: `wtype` or `ydotool`
- Clipboard (for `--once --copy`): `xclip`
- Tray icon dependencies (for default tray mode):
  - GTK + GI bindings (`python3-gi`)
  - Ayatana indicator bindings (`gir1.2-ayatanaappindicator3-0.1` or equivalent for your distro)

## Install

The repo ships with an installer script that installs into a standalone venv at `~/.local/share/dictate`, links `~/.local/bin/dictate`, and creates a desktop entry.

```bash
./install.sh
```

Installer verification can be skipped if needed:

```bash
./install.sh --no-verify
```

Optional: install NVIDIA NeMo backend dependencies in your active environment:

```bash
uv pip install -e ".[nemo]"
```

## Usage

Tray mode (default):

```bash
dictate
```

Headless daemon (no tray icon):

```bash
dictate --no-tray
```

One-shot (record until Enter, print to stdout):

```bash
dictate --once
```

One-shot (record until Enter, copy to clipboard):

```bash
dictate --once --copy
```

Run diagnostics:

```bash
dictate doctor --quick
dictate doctor --check-model-load
```

Select model/device/language:

```bash
# default faster-whisper model is "base" (quickest cold-start, reliable offline if cached)
dictate --stt-backend faster-whisper --model large-v3-turbo
dictate --stt-backend nemo-canary --model nvidia/canary-1b-flash
dictate --device cpu
dictate --language en
```

## STT Backends (RTX 4090)

Recommended defaults for low-latency dictation:

- Best balance of accuracy + speed: `nemo-canary` with `nvidia/canary-1b-flash`
- Best compatibility + hotword biasing: `faster-whisper` with `large-v3-turbo`

Examples:

```bash
# Fast, high-accuracy Canary path (recommended on RTX 4090)
dictate --stt-backend nemo-canary --model nvidia/canary-1b-flash --language en

# Canary v2 (often better quality than Canary 1B, but usually heavier)
dictate --stt-backend nemo-canary --model nvidia/canary-1b-v2 --language en

# Faster-whisper baseline with Whisper Turbo
dictate --stt-backend faster-whisper --model large-v3-turbo --language en
```

Force typing backend (daemon modes):

```bash
dictate --type-backend xdotool
dictate --type-backend wtype
dictate --type-backend ydotool
```

## Hotwords

Hotwords improve recognition of custom vocabulary (project names, technical terms, etc.) that Whisper might otherwise mishear.

Hotwords are currently applied only on the `faster-whisper` backend.

Manage saved hotwords:

```bash
dictate --add-hotword Kubernetes
dictate --add-hotword OpenBao,Vikunja
dictate --remove-hotword Vikunja
dictate --list-hotwords
```

Hotwords are saved to `~/.config/dictate/config.yaml`.

You can also pass one-off hotwords without saving them:

```bash
dictate --hotwords "Kubernetes,OpenBao"
```

CLI `--hotwords` and saved hotwords are merged at startup.

## How It Works

**Hold Right Ctrl** to record, **release** to transcribe and type into the focused window.

In tray mode, a microphone icon appears in the system tray with a right-click menu:

- **Dictation active** — checkbox to pause/resume listening for the hotkey. The icon switches to a muted microphone when paused.
- **Speech Model** — switch backend/model live. Successful changes are saved for future startups.
- If switching fails, Dictate keeps the previous model active and shows an error dialog.
- **Quit** — stops the daemon.

You can also quit from the terminal with `Ctrl+C`.

## Notes And Troubleshooting

- First run will likely download model files (Whisper or NeMo, depending on backend). Network is required once per model.
- Tray model selections are persisted in `~/.config/dictate/config.yaml` and used on startup unless CLI model flags are provided.
- Preflight now checks STT backend readiness (dependency imports + CUDA visibility) before model load.
- Startup stderr is mirrored to logs:
  - latest run: `~/.local/share/dictate/logs/latest.log`
  - last non-zero exit: `~/.local/share/dictate/logs/last_failure.log`
  - fallback when home path is not writable: `/tmp/dictate-logs/`
- On Wayland:
  - `xdotool` generally will not work for native Wayland apps.
  - Prefer `wtype` (simple) or `ydotool` (may require extra setup/permissions).
  - Global hotkeys can be restricted on some Wayland compositors; if the hotkey does not fire, use `--once` or run an X11 session.
- If preflight reports missing tools, install them via your distro package manager (e.g. `xdotool`, `xclip`, `wtype`).
- Dictation uses the system default microphone input device. If your default input is misconfigured, fix it in your OS audio settings.
- If NeMo backend fails to load, install optional deps with `uv pip install -e ".[nemo]"`.
- If the app does not launch from GUI, run `dictate doctor --quick` and inspect the reported active log directory (`~/.local/share/dictate/logs/` or `/tmp/dictate-logs/`).

## Benchmarking

Use the local benchmark harness to compare backends/models on your own accent and vocabulary:

```bash
dictate benchmark \
  --manifest benchmarks/example_manifest.csv \
  --audio-root benchmarks \
  --stt-backend nemo-canary \
  --model nvidia/canary-1b-flash \
  --device cuda \
  --language en
```

Legacy wrapper still works:

```bash
uv run python scripts/benchmark_stt.py --help
```

Create your own manifest with Australian-accent phrases and proper nouns. Format docs: `benchmarks/README.md`.

## Testing

Run regression tests:

```bash
uv run python -m unittest discover -s tests
```

## Development

- Entry point: `dictate` is `dictate.__main__:main_with_logging` (see `src/dictate/__main__.py`).
- Core pipeline modules:
  - audio capture: `src/dictate/audio.py`
  - transcription engine: `src/dictate/engine.py`
  - typing/clipboard outputs: `src/dictate/outputs.py`
  - environment checks: `src/dictate/preflight.py`
  - STT backends + registry: `src/dictate/stt/`

## License

MIT (see `LICENSE`).
