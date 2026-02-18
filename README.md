# dictate

Local voice-to-text for Linux: hold `Right Ctrl`, speak, release to transcribe and type into the focused window.

This is intended to be an always-available desktop utility (tray icon) and a CLI-friendly one-shot recorder.

## Features

- Local speech-to-text with selectable backends:
  - `faster-whisper` (default)
  - `nemo-canary` (`nvidia/canary-1b`, `nvidia/canary-1b-flash`, `nvidia/canary-1b-v2`)
- Push-to-talk daemon: `Right Ctrl` hold/release to record/transcribe/type.
- System tray toggle (pause/resume dictation).
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

Select model/device/language:

```bash
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

Hotwords are saved to `~/.config/dictate/config.yaml`. You need to restart dictate after adding or removing hotwords.

You can also pass one-off hotwords without saving them:

```bash
dictate --hotwords "Kubernetes,OpenBao"
```

CLI `--hotwords` and saved hotwords are merged at startup.

## How It Works

**Hold Right Ctrl** to record, **release** to transcribe and type into the focused window.

In tray mode, a microphone icon appears in the system tray with a right-click menu:

- **Dictation active** — checkbox to pause/resume listening for the hotkey. The icon switches to a muted microphone when paused.
- **Quit** — stops the daemon.

You can also quit from the terminal with `Ctrl+C`.

## Notes And Troubleshooting

- First run will likely download model files (Whisper or NeMo, depending on backend). Network is required once per model.
- On Wayland:
  - `xdotool` generally will not work for native Wayland apps.
  - Prefer `wtype` (simple) or `ydotool` (may require extra setup/permissions).
  - Global hotkeys can be restricted on some Wayland compositors; if the hotkey does not fire, use `--once` or run an X11 session.
- If preflight reports missing tools, install them via your distro package manager (e.g. `xdotool`, `xclip`, `wtype`).
- Dictation uses the system default microphone input device. If your default input is misconfigured, fix it in your OS audio settings.
- If NeMo backend fails to load, install optional deps with `uv pip install -e ".[nemo]"`.

## Development

- Entry point: `dictate` is `dictate.__main__:main` (see `src/dictate/__main__.py`).
- Core pipeline modules:
  - audio capture: `src/dictate/audio.py`
  - transcription engine: `src/dictate/engine.py`
  - typing/clipboard outputs: `src/dictate/outputs.py`
  - environment checks: `src/dictate/preflight.py`

## License

MIT (see `LICENSE`).
