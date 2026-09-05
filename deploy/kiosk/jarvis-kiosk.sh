#!/usr/bin/env bash
# Chromium kiosk fallback. The product HUD is the Tauri window.
set -euo pipefail
if [[ -n "${JARVIS_ROOT:-}" && -d "$JARVIS_ROOT/desktop/ui" ]]; then
  ROOT="$JARVIS_ROOT"
elif [[ -d "${HOME}/.local/share/jarvis/src/desktop/ui" ]]; then
  ROOT="${HOME}/.local/share/jarvis/src"
else
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi
PORT="${JARVIS_KIOSK_PORT:-4173}"
URL="http://127.0.0.1:${PORT}/"
DATA="${JARVIS_KIOSK_PROFILE:-$HOME/.local/share/jarvis/kiosk}"
mkdir -p "$DATA"
cd "$ROOT/desktop/ui"
python3 -m http.server "$PORT" --bind 127.0.0.1 >/tmp/jarvis-kiosk-http.log 2>&1 &
HTTP_PID=$!
cleanup() { kill "$HTTP_PID" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 40); do
  if curl -sf "$URL" >/dev/null; then
    break
  fi
  sleep 0.15
done
CHROME=""
for bin in google-chrome-stable google-chrome brave-browser chromium chromium-browser firefox; do
  if command -v "$bin" >/dev/null; then
    CHROME="$bin"
    break
  fi
done
if [[ -z "$CHROME" ]]; then
  echo "No Chrome/Firefox. Do not apt-install chromium-browser on Pop 24.04 (snap). Build Tauri or install Google Chrome." >&2
  exit 1
fi
if [[ "$CHROME" == *firefox* ]]; then
  exec "$CHROME" --kiosk --profile "$DATA" "$URL"
fi
exec "$CHROME" \
  --user-data-dir="$DATA" \
  --no-first-run \
  --disable-session-crashed-bubble \
  --kiosk \
  --app="$URL"
