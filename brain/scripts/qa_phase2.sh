#!/usr/bin/env bash
# Mandatory Phase 2 QA: real Piper audio, then optional Hermes turn + WAV.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT/brain/src${PYTHONPATH:+:$PYTHONPATH}"
export JARVIS_TTS_PROVIDER="${JARVIS_TTS_PROVIDER:-piper}"
export JARVIS_TTS_FALLBACK=piper
EVIDENCE="${JARVIS_QA_EVIDENCE:-/tmp/jarvis-phase2-qa.txt}"
WAV="${JARVIS_QA_WAV:-/tmp/jarvis-phase2.wav}"
PY="${PYTHON:-python3}"

bash "$ROOT/brain/scripts/setup_piper.sh"
# shellcheck disable=SC1091
export JARVIS_PIPER_BIN="${JARVIS_PIPER_BIN:-$HOME/.local/share/jarvis/piper/piper/piper}"
export JARVIS_PIPER_MODEL="${JARVIS_PIPER_MODEL:-$HOME/.local/share/jarvis/piper/voices/es_ES-davefx-medium.onnx}"
export JARVIS_PIPER_ESPEAK="${JARVIS_PIPER_ESPEAK:-$HOME/.local/share/jarvis/piper/piper/espeak-ng-data}"

{
  echo "=== Phase 2 QA: local TTS $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "provider=$JARVIS_TTS_PROVIDER piper=$JARVIS_PIPER_BIN"
} | tee "$EVIDENCE"

set +e
SPEAK_OUT="$("$PY" -m jarvis_brain speak -m "Sistemas en línea. Fase dos verificada." --wav "$WAV" 2>&1)"
SPEAK_RC=$?
set -e
printf '%s\n' "$SPEAK_OUT" | tee -a "$EVIDENCE"

if [[ "$SPEAK_RC" -ne 0 ]]; then
  echo "FAIL: speak exited $SPEAK_RC" | tee -a "$EVIDENCE"
  exit 1
fi
if ! printf '%s\n' "$SPEAK_OUT" | grep -q "QA: local TTS audible"; then
  echo "FAIL: speak did not confirm audible PCM" | tee -a "$EVIDENCE"
  exit 1
fi

echo "=== ffprobe ===" | tee -a "$EVIDENCE"
ffprobe -hide_banner "$WAV" 2>&1 | tee -a "$EVIDENCE" || true

if curl -fsS -H "Authorization: Bearer ${API_SERVER_KEY:-jarvis-phase1-key}" \
     "${JARVIS_HERMES_URL:-http://127.0.0.1:8642}/health" >/dev/null 2>&1; then
  echo "=== chat + TTS ===" | tee -a "$EVIDENCE"
  TURN_WAV="${JARVIS_QA_TURN_WAV:-/tmp/jarvis-phase2-turn.wav}"
  set +e
  CHAT_OUT="$(cd "$ROOT/brain" && API_SERVER_KEY="${API_SERVER_KEY:-jarvis-phase1-key}" \
    JARVIS_HERMES_URL="${JARVIS_HERMES_URL:-http://127.0.0.1:8642}" \
    JARVIS_TTS_PROVIDER=piper \
    "$PY" -m jarvis_brain chat --wav "$TURN_WAV" -m "hola, di que sistemas en linea" 2>&1)"
  CHAT_RC=$?
  set -e
  printf '%s\n' "$CHAT_OUT" | tee -a "$EVIDENCE"
  if [[ "$CHAT_RC" -ne 0 ]] || ! printf '%s\n' "$CHAT_OUT" | grep -q JARVIS_PHASE1_OK; then
    echo "FAIL: chat+TTS" | tee -a "$EVIDENCE"
    exit 1
  fi
else
  echo "Hermes not up — skipped chat+TTS (speak path verified)." | tee -a "$EVIDENCE"
fi

echo "PASS: Phase 2 local TTS" | tee -a "$EVIDENCE"
echo "evidence: $EVIDENCE wav: $WAV"
