#!/usr/bin/env bash
# Install/update dictate as a system-wide tool via uv.
# Re-run this script after pulling changes to update the installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

echo "Installing dictate from $SCRIPT_DIR ..."
uv tool install "$SCRIPT_DIR" --force

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
Keywords=voice;speech;transcription;dictation;whisper;
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Done. 'dictate' is now available on your PATH and in the app launcher."
