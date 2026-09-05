#!/usr/bin/env bash
# User-level systemd + kiosk desktop entry for Pop!_OS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/jarvis"
mkdir -p "$UNIT_DIR" "$APP_DIR" "$BIN_DIR" "$SHARE/voices" "$SHARE/src"
ln -sfn "$ROOT" "$SHARE/src"
PY="${PYTHON:-python3}"
sed \
  -e "s|WorkingDirectory=.*|WorkingDirectory=$ROOT/brain|" \
  -e "s|ExecStart=.*python3 -m jarvis_brain serve|ExecStart=$PY -m jarvis_brain serve|" \
  "$ROOT/deploy/systemd/jarvis-brain.service" > "$UNIT_DIR/jarvis-brain.service"
sed \
  -e "s|Documentation=.*DETECT.md|Documentation=file://$ROOT/docs/DETECT.md|" \
  "$ROOT/deploy/systemd/jarvis-door.service" > "$UNIT_DIR/jarvis-door.service"
cp "$ROOT/deploy/systemd/jarvis.service" "$UNIT_DIR/jarvis.service"
install -m 0755 "$ROOT/deploy/kiosk/jarvis-kiosk.sh" "$BIN_DIR/jarvis-kiosk"
sed "s|^Exec=.*|Exec=$BIN_DIR/jarvis-kiosk|" \
  "$ROOT/deploy/kiosk/jarvis-kiosk.desktop" > "$APP_DIR/jarvis-kiosk.desktop"
for name in jarvis companion; do
  src="$ROOT/voices/${name}.wav"
  dest="$SHARE/voices/${name}.wav"
  if [[ -f "$src" && ! -f "$dest" ]]; then
    cp "$src" "$dest"
  fi
done
systemctl --user daemon-reload
echo "User units:"
echo "  systemctl --user enable --now jarvis-brain.service"
echo "  systemctl --user enable jarvis-door.service   # only if JARVIS_YOLO_DETECT is set"
echo "Kiosk fallback: jarvis-kiosk  (Tauri remains the product HUD)"
echo "Voice WAVs: $SHARE/voices/{jarvis,companion}.wav  (placeholders; clone needs ≥5s speech)"
