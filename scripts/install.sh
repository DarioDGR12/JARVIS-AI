#!/usr/bin/env bash
# Pop!_OS first install: brain + Piper + user units + HUD (Tauri if possible).
#   bash scripts/install.sh
#   bash scripts/install.sh --apt --hermes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
DO_APT=0
DO_HERMES=0
DO_STT=0
DO_TAURI=1
for arg in "$@"; do
  case "$arg" in
    --apt) DO_APT=1 ;;
    --hermes) DO_HERMES=1 ;;
    --stt) DO_STT=1 ;;
    --no-tauri) DO_TAURI=0 ;;
    -h|--help)
      echo "Usage: bash scripts/install.sh [--apt] [--hermes] [--stt] [--no-tauri]"
      exit 0
      ;;
  esac
done

if [[ "$DO_APT" -eq 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y \
    python3-pip python3-venv python3-dev \
    curl git pkg-config libssl-dev build-essential \
    tesseract-ocr tesseract-ocr-spa ffmpeg xdotool \
    chromium-browser \
    libwebkit2gtk-4.1-dev || sudo apt-get install -y libwebkit2gtk-4.0-dev || true
fi

"$PY" -m pip install -e "$ROOT/brain"
if [[ "$DO_STT" -eq 1 ]]; then
  bash "$ROOT/brain/scripts/install_stt.sh"
fi
bash "$ROOT/brain/scripts/setup_piper.sh"
"$PY" "$ROOT/desktop/scripts/generate_icons.py" || true

if [[ "$DO_HERMES" -eq 1 ]]; then
  bash "$ROOT/scripts/install-hermes.sh"
elif [[ ! -x "${HERMES_BIN:-}" ]] && ! command -v hermes >/dev/null \
  && [[ ! -x /tmp/hermes-agent-src/.venv/bin/hermes ]] \
  && [[ ! -x "$HOME/.local/share/jarvis/hermes-agent/.venv/bin/hermes" ]] \
  && [[ ! -x "$HOME/.local/bin/hermes" ]]; then
  echo "Hermes Agent is not on PATH."
  echo "  bash scripts/install-hermes.sh"
  echo "  or: export HERMES_BIN=/path/to/.venv/bin/hermes"
fi

if [[ "$DO_TAURI" -eq 1 ]] && command -v npm >/dev/null && command -v cargo >/dev/null; then
  (cd "$ROOT/desktop" && npm install && npx tauri build --debug)
elif [[ "$DO_TAURI" -eq 1 ]]; then
  echo "npm/cargo missing: HUD will use Chromium kiosk until you build Tauri."
  echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
  echo "  then: cd desktop && npm install && npx tauri build"
fi

bash "$ROOT/scripts/install-user.sh"

export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
if ! "$PY" -c "import jarvis_brain" 2>/dev/null; then
  echo "pip install -e brain failed" >&2
  exit 1
fi
if [[ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/jarvis/product.yaml" ]]; then
  "$PY" -m jarvis_brain setup --demo || true
fi

echo
echo "Install done. Next:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo "  jarvis doctor"
echo "  jarvis start          # Tauri, or Chromium kiosk if not built"
echo "Guide: docs/POPOS.md"
