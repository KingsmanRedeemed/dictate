#!/usr/bin/env bash
# Install/update dictate into a standalone venv at ~/.local/share/dictate.
# Uses --system-site-packages so GTK/gi bindings are available.
# Re-run this script after pulling changes to update the installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/dictate"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
VERIFY=1

if [ "${1:-}" = "--no-verify" ]; then
  VERIFY=0
  shift
fi

if [ "$#" -ne 0 ]; then
  echo "Usage: $0 [--no-verify]"
  exit 1
fi

echo "Creating venv at $INSTALL_DIR ..."
uv venv "$INSTALL_DIR/venv" --python python3 --system-site-packages --quiet

echo "Installing dictate from $SCRIPT_DIR ..."
uv pip install "$SCRIPT_DIR" --python "$INSTALL_DIR/venv/bin/python" --quiet

echo "Linking binary ..."
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/venv/bin/dictate" "$BIN_DIR/dictate"

echo "Installing desktop entry ..."
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/dictate.desktop" <<EOF
[Desktop Entry]
Name=Dictate
Comment=Local voice-to-text with push-to-talk
Exec=$HOME/.local/bin/dictate
Icon=microphone-sensitivity-high-symbolic
Type=Application
Categories=Utility;Audio;
Keywords=voice;speech;transcription;dictation;asr;whisper;canary;
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

if [ "$VERIFY" -eq 1 ]; then
  VERIFY_LOG="/tmp/dictate-install-verify.log"
  DICTATE_BIN="$INSTALL_DIR/venv/bin/dictate"

  run_check() {
    local label="$1"
    shift
    echo "Verifying: $label ..."
    if command -v timeout >/dev/null 2>&1; then
      if ! timeout 20s "$@" >"$VERIFY_LOG" 2>&1; then
        echo "Verification failed: $label"
        echo "See: $VERIFY_LOG"
        tail -n 120 "$VERIFY_LOG" || true
        exit 1
      fi
    else
      if ! "$@" >"$VERIFY_LOG" 2>&1; then
        echo "Verification failed: $label"
        echo "See: $VERIFY_LOG"
        tail -n 120 "$VERIFY_LOG" || true
        exit 1
      fi
    fi
  }

  run_check "dictate --help" "$DICTATE_BIN" --help
  run_check "dictate benchmark --help" "$DICTATE_BIN" benchmark --help
  run_check "dictate doctor --quick" "$DICTATE_BIN" doctor --quick
fi

echo "Done. 'dictate' is now available on your PATH and in the app launcher."
