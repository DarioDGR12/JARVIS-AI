#!/usr/bin/env bash
# First-run on Pop!_OS. Does not download YOLO or ElevenLabs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/install.sh" "$@"
export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
export JARVIS_BUS_HOST="${JARVIS_BUS_HOST:-127.0.0.1}"
python3 -m jarvis_brain setup --demo
set +e
python3 -m jarvis_brain doctor
rc=$?
set -e
echo
echo "Si doctor está listo:  jarvis start"
echo "Sin Tauri:             jarvis start --hud kiosk"
echo "Guía: $ROOT/docs/POPOS.md"
exit "$rc"
