#!/usr/bin/env bash
# Start mock LLM + Hermes API server for Phase 1 text turns.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERMES_SRC="${HERMES_SRC:-/tmp/hermes-agent-src}"
HERMES_BIN="${HERMES_BIN:-$HERMES_SRC/.venv/bin/hermes}"
export HOME_HERMES="${HOME}/.hermes"
mkdir -p "$HOME_HERMES"

# Hermes refuses API_SERVER_KEY shorter than 16 characters (silent skip).
export API_SERVER_ENABLED=true
export API_SERVER_KEY="${API_SERVER_KEY:-jarvis-phase1-key}"
export API_SERVER_HOST="${API_SERVER_HOST:-127.0.0.1}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-local}"
export JARVIS_HERMES_KEY="$API_SERVER_KEY"
export JARVIS_HERMES_URL="http://${API_SERVER_HOST}:${API_SERVER_PORT}"

if (( ${#API_SERVER_KEY} < 16 )); then
  echo "API_SERVER_KEY must be >= 16 chars (Hermes startup guard). Got ${#API_SERVER_KEY}." >&2
  exit 1
fi

cat > "$HOME_HERMES/.env" <<EOF
API_SERVER_ENABLED=true
API_SERVER_KEY=${API_SERVER_KEY}
API_SERVER_HOST=${API_SERVER_HOST}
API_SERVER_PORT=${API_SERVER_PORT}
OPENAI_API_KEY=${OPENAI_API_KEY}
EOF

cat > "$HOME_HERMES/config.yaml" <<EOF
model:
  provider: custom
  model: mock-jarvis
  base_url: http://127.0.0.1:18765/v1
  api_key: sk-local
  context_length: 8192
  streaming: false
EOF

if ! curl -fsS http://127.0.0.1:18765/health >/dev/null 2>&1; then
  python3 "$ROOT/brain/scripts/mock_openai_llm.py" &
  echo $! > /tmp/jarvis-mock-llm.pid
  sleep 0.3
else
  echo "mock LLM already on :18765"
fi

if [[ ! -x "$HERMES_BIN" ]]; then
  echo "Hermes binary not found at $HERMES_BIN" >&2
  echo "Install: cd /tmp && git clone --depth 1 https://github.com/NousResearch/hermes-agent.git hermes-agent-src && cd hermes-agent-src && uv sync --no-dev" >&2
  exit 1
fi

if curl -fsS -H "Authorization: Bearer ${API_SERVER_KEY}" \
     "${JARVIS_HERMES_URL}/v1/models" >/dev/null 2>&1; then
  echo "Hermes API already on ${JARVIS_HERMES_URL}"
else
  "$HERMES_BIN" gateway run --replace &
  echo $! > /tmp/jarvis-hermes.pid
  echo "waiting for Hermes API on ${JARVIS_HERMES_URL} ..."
  for i in $(seq 1 60); do
    if curl -fsS -H "Authorization: Bearer ${API_SERVER_KEY}" \
         "${JARVIS_HERMES_URL}/v1/models" >/dev/null 2>&1; then
      echo "Hermes API listening on ${JARVIS_HERMES_URL}"
      break
    fi
    sleep 1
    if [[ "$i" -eq 60 ]]; then
      echo "Hermes API did not come up on ${JARVIS_HERMES_URL}" >&2
      echo "Check ~/.hermes/logs/gateway.log — API_SERVER_KEY must be >= 16 chars." >&2
      exit 1
    fi
  done
fi

echo "Then: cd $ROOT/brain && API_SERVER_KEY=$API_SERVER_KEY python -m jarvis_brain chat -m 'hola'"
