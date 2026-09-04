#!/usr/bin/env bash
# Install JARVIS as a local product (brain + Piper). Hermes is a sibling install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
"$PY" -m pip install -e "$ROOT/brain"
bash "$ROOT/brain/scripts/setup_piper.sh"
if [[ ! -x "${HERMES_BIN:-/tmp/hermes-agent-src/.venv/bin/hermes}" ]] && ! command -v hermes >/dev/null; then
  echo "Hermes Agent is not on PATH."
  echo "Install once: git clone --depth 1 https://github.com/NousResearch/hermes-agent.git && cd hermes-agent && uv sync --no-dev"
  echo "Then: export HERMES_BIN=/path/to/hermes"
fi
echo
echo "Next:"
echo "  jarvis setup --demo                          # try without a cloud key"
echo "  jarvis setup --provider openai --api-key sk-...   # BYOK"
echo "  jarvis start                                 # http://127.0.0.1:8765/"
