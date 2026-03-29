#!/usr/bin/env bash
# Install/update dictate into a standalone venv at ~/.local/share/dictate.
# Uses --system-site-packages so GTK/gi bindings are available.
# Re-run this script after pulling changes to update the installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/dictate"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/dictate"
CONFIG_PATH="$CONFIG_DIR/config.yaml"
DEFAULT_CONFIG_SOURCE="$SCRIPT_DIR/config/default-config.yaml"
VERIFY=1
PREPARE_TURBO=1
SEED_DEFAULT_CONFIG=1
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Prefer the distro Python so --system-site-packages can see modules such as
# python3-gi from /usr/lib/python3/dist-packages.
if [ -x /usr/bin/python3 ]; then
  PYTHON_BIN="/usr/bin/python3"
fi

usage() {
  cat <<EOF
Usage: $0 [--no-verify] [--no-prepare-turbo] [--no-seed-default-config]

Installs dictate into ~/.local/share/dictate, links ~/.local/bin/dictate,
seeds the default config on first install, and prepares the faster-whisper
turbo model unless disabled.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-verify)
      VERIFY=0
      ;;
    --no-prepare-turbo)
      PREPARE_TURBO=0
      ;;
    --no-seed-default-config)
      SEED_DEFAULT_CONFIG=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 1
      ;;
  esac
  shift
done

echo "Creating venv at $INSTALL_DIR ..."
uv venv "$INSTALL_DIR/venv" --python "$PYTHON_BIN" --system-site-packages --quiet

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

if [ "$SEED_DEFAULT_CONFIG" -eq 1 ]; then
  if [ ! -f "$CONFIG_PATH" ]; then
    if [ ! -f "$DEFAULT_CONFIG_SOURCE" ]; then
      echo "Default config template not found: $DEFAULT_CONFIG_SOURCE"
      exit 1
    fi
    echo "Seeding default config at $CONFIG_PATH ..."
    mkdir -p "$CONFIG_DIR"
    install -m 600 "$DEFAULT_CONFIG_SOURCE" "$CONFIG_PATH"
  else
    echo "Existing config found at $CONFIG_PATH; leaving it unchanged."
  fi
fi

DICTATE_BIN="$INSTALL_DIR/venv/bin/dictate"

run_logged_check() {
  local label="$1"
  local log_path="$2"
  local timeout_seconds="$3"
  shift 3
  echo "Running: $label ..."
  if command -v timeout >/dev/null 2>&1; then
    if ! timeout "${timeout_seconds}s" "$@" >"$log_path" 2>&1; then
      echo "Command failed: $label"
      echo "See: $log_path"
      tail -n 120 "$log_path" || true
      exit 1
    fi
  else
    if ! "$@" >"$log_path" 2>&1; then
      echo "Command failed: $label"
      echo "See: $log_path"
      tail -n 120 "$log_path" || true
      exit 1
    fi
  fi
}

if [ "$PREPARE_TURBO" -eq 1 ]; then
  PREPARE_LOG="/tmp/dictate-install-prepare.log"
  run_logged_check \
    "dictate prepare-model --stt-backend faster-whisper --model turbo --device auto --compute-type int8" \
    "$PREPARE_LOG" \
    1800 \
    "$DICTATE_BIN" \
    prepare-model \
    --stt-backend faster-whisper \
    --model turbo \
    --device auto \
    --compute-type int8
fi

if [ "$VERIFY" -eq 1 ]; then
  VERIFY_LOG="/tmp/dictate-install-verify.log"
  run_logged_check "dictate --help" "$VERIFY_LOG" 20 "$DICTATE_BIN" --help
  run_logged_check "dictate benchmark --help" "$VERIFY_LOG" 20 "$DICTATE_BIN" benchmark --help
  run_logged_check \
    "dictate doctor --quick --stt-backend faster-whisper --model turbo" \
    "$VERIFY_LOG" \
    20 \
    "$DICTATE_BIN" \
    doctor \
    --quick \
    --stt-backend faster-whisper \
    --model turbo
fi

echo "Done. 'dictate' is now available on your PATH and in the app launcher."
