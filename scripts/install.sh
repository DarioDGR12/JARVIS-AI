#!/usr/bin/env bash
# Pop!_OS first install: venv + Piper + user units + HUD.
# Never pip-installs into the system Python (PEP 668).
# Never apt-installs chromium-browser (Noble snap; times out).
#   bash scripts/install.sh
#   bash scripts/install.sh --apt --hermes
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${JARVIS_VENV:-$HOME/.local/share/jarvis/venv}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
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
  sudo dpkg --configure -a || true
  sudo apt-get -f install -y || true
  sudo apt-get install -y \
    python3-venv python3-dev python3-full \
    curl git pkg-config libssl-dev build-essential \
    tesseract-ocr tesseract-ocr-spa ffmpeg xdotool \
    libwebkit2gtk-4.1-dev
fi

mkdir -p "$(dirname "$VENV")" "$BIN_DIR"
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -U pip wheel
"$VENV/bin/pip" install -e "$ROOT/brain"
if [[ "$DO_STT" -eq 1 ]]; then
  "$VENV/bin/pip" install -e "$ROOT/brain[stt]"
fi
ln -sfn "$VENV/bin/jarvis" "$BIN_DIR/jarvis"
export PATH="$BIN_DIR:$PATH"
export PYTHON="$VENV/bin/python"

bash "$ROOT/brain/scripts/setup_piper.sh"
"$VENV/bin/python" "$ROOT/desktop/scripts/generate_icons.py" || true

if [[ "$DO_HERMES" -eq 1 ]]; then
  if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  bash "$ROOT/scripts/install-hermes.sh"
elif [[ ! -x "${HERMES_BIN:-}" ]] && ! command -v hermes >/dev/null \
  && [[ ! -x "$HOME/.local/share/jarvis/hermes-agent/.venv/bin/hermes" ]] \
  && [[ ! -x "$HOME/.local/bin/hermes" ]]; then
  echo "Hermes Agent is not on PATH."
  echo "  bash scripts/install-hermes.sh"
fi

if [[ "$DO_TAURI" -eq 1 ]] && command -v npm >/dev/null && command -v cargo >/dev/null; then
  (cd "$ROOT/desktop" && npm install && npx tauri build --debug)
elif [[ "$DO_TAURI" -eq 1 ]]; then
  echo "npm/cargo missing: HUD will use the kiosk (Chrome / Firefox) until you build Tauri."
fi

export PYTHON="$VENV/bin/python"
bash "$ROOT/scripts/install-user.sh"

if ! "$VENV/bin/python" -c "import jarvis_brain" 2>/dev/null; then
  echo "venv install failed: $VENV" >&2
  exit 1
fi
if [[ ! -f "${XDG_CONFIG_HOME:-$HOME/.config}/jarvis/product.yaml" ]]; then
  "$VENV/bin/jarvis" setup --demo || true
fi

echo
echo "Install done. Next:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "  jarvis doctor"
echo "  jarvis start"
echo "Python: $VENV/bin/python"
echo "Guide: docs/POPOS.md"
