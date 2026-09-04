#!/usr/bin/env bash
# Install JARVIS as a desktop product (brain + Piper + Tauri app).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -m pip install -e "$ROOT/brain"
bash "$ROOT/brain/scripts/setup_piper.sh"
python3 "$ROOT/desktop/scripts/generate_icons.py"
if [[ ! -x "${HERMES_BIN:-/tmp/hermes-agent-src/.venv/bin/hermes}" ]] && ! command -v hermes >/dev/null; then
  echo "Hermes Agent is not on PATH."
  echo "Install once: git clone --depth 1 https://github.com/NousResearch/hermes-agent.git && cd hermes-agent && uv sync --no-dev"
  echo "Then: export HERMES_BIN=/path/to/hermes"
fi
if command -v npm >/dev/null && command -v cargo >/dev/null; then
  (cd "$ROOT/desktop" && npm install && npx tauri build --debug)
else
  echo "npm/cargo missing: the desktop window will not build. Install Rust + Node."
fi
echo
echo "Next:"
echo "  jarvis setup --demo"
echo "  jarvis start                                 # opens the Tauri app"
