# dictate

Local voice-to-text for Linux: hold `Right Ctrl`, speak, release to transcribe and type into the focused window.

This is intended to be an always-available desktop utility (tray icon) and a CLI-friendly one-shot recorder.

## Features

- Local speech-to-text via `faster-whisper` (model loads once; stays in memory for low latency).
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
dictate --model small
dictate --device cpu
dictate --language en
```

Force typing backend (daemon modes):

```bash
dictate --type-backend xdotool
dictate --type-backend wtype
dictate --type-backend ydotool
```

## Notes And Troubleshooting

- First run will likely download Whisper model files (network required once).
- On Wayland:
  - `xdotool` generally will not work for native Wayland apps.
  - Prefer `wtype` (simple) or `ydotool` (may require extra setup/permissions).
  - Global hotkeys can be restricted on some Wayland compositors; if the hotkey does not fire, use `--once` or run an X11 session.
- If preflight reports missing tools, install them via your distro package manager (e.g. `xdotool`, `xclip`, `wtype`).
- Dictation uses the system default microphone input device. If your default input is misconfigured, fix it in your OS audio settings.

## Development

- Entry point: `dictate` is `dictate.__main__:main` (see `src/dictate/__main__.py`).
- Core pipeline modules:
  - audio capture: `src/dictate/audio.py`
  - transcription engine: `src/dictate/engine.py`
  - typing/clipboard outputs: `src/dictate/outputs.py`
  - environment checks: `src/dictate/preflight.py`

## License

MIT (see `LICENSE`).

