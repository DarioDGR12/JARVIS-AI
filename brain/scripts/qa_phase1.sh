#!/usr/bin/env bash
# Mandatory Phase 1 QA: real text turn through Hermes + bus.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export API_SERVER_KEY="${API_SERVER_KEY:-jarvis-phase1-key}"
export JARVIS_HERMES_KEY="$API_SERVER_KEY"
export JARVIS_HERMES_URL="${JARVIS_HERMES_URL:-http://127.0.0.1:8642}"
export JARVIS_BUS_HOST="${JARVIS_BUS_HOST:-127.0.0.1}"
export JARVIS_BUS_PORT="${JARVIS_BUS_PORT:-8765}"
export PYTHONPATH="$ROOT/brain/src${PYTHONPATH:+:$PYTHONPATH}"
EVIDENCE="${JARVIS_QA_EVIDENCE:-/tmp/jarvis-phase1-qa.txt}"

bash "$ROOT/brain/scripts/run_phase1_stack.sh"

echo "=== Phase 1 QA: text turn ===" | tee "$EVIDENCE"
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "hermes: $JARVIS_HERMES_URL"
  echo "key_len: ${#API_SERVER_KEY}"
} | tee -a "$EVIDENCE"

set +e
CHAT_OUT="$(cd "$ROOT/brain" && python -m jarvis_brain chat -m "hola, prueba de fase 1" 2>&1)"
CHAT_RC=$?
set -e
printf '%s\n' "$CHAT_OUT" | tee -a "$EVIDENCE"

echo "=== mock LLM health ===" | tee -a "$EVIDENCE"
curl -fsS http://127.0.0.1:18765/health | tee -a "$EVIDENCE"
echo | tee -a "$EVIDENCE"
if [[ -f /tmp/jarvis-mock-llm-last.json ]]; then
  echo "=== last mock request ===" | tee -a "$EVIDENCE"
  cat /tmp/jarvis-mock-llm-last.json | tee -a "$EVIDENCE"
  echo | tee -a "$EVIDENCE"
fi

echo "=== bus HTTP ===" | tee -a "$EVIDENCE"
python - <<'PY' | tee -a "$EVIDENCE"
from fastapi.testclient import TestClient
from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
bus = EventBus()
c = TestClient(bus.app())
print("health", c.get("/health").json())
body = new_event("user.text", {"text": "bus-qa"}, source="qa").to_dict()
r = c.post("/api/bus", json=body)
print("post", r.status_code, r.json()["type"])
with c.websocket_connect("/ws/bus") as ws:
    ws.send_json(body)
    echoed = ws.receive_json()
print("ws", echoed["type"], echoed["payload"]["text"])
PY

if [[ "$CHAT_RC" -ne 0 ]]; then
  echo "FAIL: chat exited $CHAT_RC" | tee -a "$EVIDENCE"
  exit 1
fi
if ! printf '%s\n' "$CHAT_OUT" | grep -q JARVIS_PHASE1_OK; then
  echo "FAIL: reply missing JARVIS_PHASE1_OK — instructions overlay not verified" | tee -a "$EVIDENCE"
  exit 1
fi
if ! printf '%s\n' "$CHAT_OUT" | grep -q "QA: instructions overlay reached the model"; then
  echo "FAIL: CLI did not confirm overlay" | tee -a "$EVIDENCE"
  exit 1
fi
echo "PASS: text turn + instructions overlay verified" | tee -a "$EVIDENCE"
echo "evidence: $EVIDENCE"
