#!/usr/bin/env bash
# User-level systemd, desktop entry, env, voices for Pop!_OS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${JARVIS_VENV:-$HOME/.local/share/jarvis/venv}"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/jarvis"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/jarvis"
mkdir -p "$UNIT_DIR" "$APP_DIR" "$BIN_DIR" "$CFG" "$SHARE/voices" "$SHARE/src"
ln -sfn "$ROOT" "$SHARE/src"
if [[ -x "$VENV/bin/python" ]]; then
  PY="$VENV/bin/python"
elif [[ -n "${PYTHON:-}" && -x "${PYTHON}" ]]; then
  PY="$PYTHON"
else
  PY="python3"
fi
PIPER_HOME="${JARVIS_PIPER_HOME:-$HOME/.local/share/jarvis/piper}"

sed \
  -e "s|WorkingDirectory=.*|WorkingDirectory=$ROOT/brain|" \
  -e "s|ExecStart=.*jarvis_brain serve|ExecStart=$PY -m jarvis_brain serve|" \
  "$ROOT/deploy/systemd/jarvis-brain.service" > "$UNIT_DIR/jarvis-brain.service"
sed \
  -e "s|Documentation=.*DETECT.md|Documentation=file://$ROOT/docs/DETECT.md|" \
  "$ROOT/deploy/systemd/jarvis-door.service" > "$UNIT_DIR/jarvis-door.service"
cp "$ROOT/deploy/systemd/jarvis.service" "$UNIT_DIR/jarvis.service"

cat > "$BIN_DIR/jarvis-kiosk" <<EOF
#!/usr/bin/env bash
export JARVIS_ROOT="$ROOT"
exec bash "$ROOT/deploy/kiosk/jarvis-kiosk.sh" "\$@"
EOF
chmod +x "$BIN_DIR/jarvis-kiosk"
if [[ -x "$VENV/bin/jarvis" ]]; then
  ln -sfn "$VENV/bin/jarvis" "$BIN_DIR/jarvis"
fi

if [[ -x "$BIN_DIR/jarvis" ]]; then
  JARVIS_BIN="$BIN_DIR/jarvis"
elif [[ -x "$VENV/bin/jarvis" ]]; then
  JARVIS_BIN="$VENV/bin/jarvis"
else
  JARVIS_BIN="$PY -m jarvis_brain"
fi
sed \
  -e "s|^Exec=.*|Exec=$JARVIS_BIN start|" \
  "$ROOT/deploy/desktop/jarvis.desktop" > "$APP_DIR/jarvis.desktop"
sed "s|^Exec=.*|Exec=$BIN_DIR/jarvis-kiosk|" \
  "$ROOT/deploy/kiosk/jarvis-kiosk.desktop" > "$APP_DIR/jarvis-kiosk.desktop"

if [[ ! -f "$CFG/brain.env" ]]; then
  {
    echo "JARVIS_BUS_HOST=127.0.0.1"
    echo "JARVIS_BUS_PORT=8765"
    echo "JARVIS_TTS_PROVIDER=piper"
    echo "JARVIS_ROOT=$ROOT"
    echo "JARVIS_VENV=$VENV"
    if [[ -x "$PIPER_HOME/piper/piper" ]]; then
      echo "JARVIS_PIPER_BIN=$PIPER_HOME/piper/piper"
      echo "JARVIS_PIPER_ESPEAK=$PIPER_HOME/piper/espeak-ng-data"
    fi
    if [[ -f "$PIPER_HOME/voices/es_ES-davefx-medium.onnx" ]]; then
      echo "JARVIS_PIPER_MODEL=$PIPER_HOME/voices/es_ES-davefx-medium.onnx"
    fi
    if [[ -x "$HOME/.local/share/jarvis/hermes-agent/.venv/bin/hermes" ]]; then
      echo "HERMES_BIN=$HOME/.local/share/jarvis/hermes-agent/.venv/bin/hermes"
    fi
  } > "$CFG/brain.env"
  chmod 600 "$CFG/brain.env"
fi

for name in jarvis companion; do
  src="$ROOT/voices/${name}.wav"
  dest="$SHARE/voices/${name}.wav"
  if [[ -f "$src" && ! -f "$dest" ]]; then
    cp "$src" "$dest"
  fi
done

if command -v systemctl >/dev/null; then
  systemctl --user daemon-reload || true
fi
echo "User units in $UNIT_DIR"
echo "  systemctl --user enable --now jarvis-brain.service"
echo "Desktop: $APP_DIR/jarvis.desktop"
echo "Env: $CFG/brain.env"
echo "Venv: $VENV"
