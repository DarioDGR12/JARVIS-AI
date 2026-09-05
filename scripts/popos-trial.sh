#!/usr/bin/env bash
# First-run on Pop!_OS. Does not download YOLO or ElevenLabs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/install.sh" "$@"
export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
export JARVIS_BUS_HOST="${JARVIS_BUS_HOST:-127.0.0.1}"
VENV="${JARVIS_VENV:-$HOME/.local/share/jarvis/venv}"
if [[ -x "$VENV/bin/jarvis" ]]; then
  JARVIS="$VENV/bin/jarvis"
elif command -v jarvis >/dev/null; then
  JARVIS="jarvis"
else
  echo "jarvis no está en $VENV ni en PATH" >&2
  exit 1
fi
"$JARVIS" setup --demo
set +e
"$JARVIS" doctor
rc=$?
set -e
echo
echo "Si doctor está listo:  export PATH=\"\$HOME/.local/bin:\$PATH\" && jarvis start"
echo "Sin Tauri:             jarvis start --hud kiosk"
echo "Guía: $ROOT/docs/POPOS.md"
exit "$rc"
