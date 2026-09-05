#!/usr/bin/env bash
# Hermes Agent once. JARVIS talks to 127.0.0.1:8642 only.
set -euo pipefail
DEST="${HERMES_SRC:-$HOME/.local/share/jarvis/hermes-agent}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [[ -x "$DEST/.venv/bin/hermes" ]]; then
  ln -sfn "$DEST/.venv/bin/hermes" "$BIN_DIR/hermes"
  echo "Hermes already at $DEST/.venv/bin/hermes"
  echo "HERMES_BIN=$DEST/.venv/bin/hermes"
  exit 0
fi
if ! command -v uv >/dev/null && ! command -v git >/dev/null; then
  echo "Need git and uv: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi
if ! command -v uv >/dev/null; then
  echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi
mkdir -p "$(dirname "$DEST")" "$BIN_DIR"
if [[ ! -d "$DEST/.git" ]]; then
  git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "$DEST"
fi
(cd "$DEST" && uv sync --no-dev)
ln -sfn "$DEST/.venv/bin/hermes" "$BIN_DIR/hermes"
echo "HERMES_BIN=$DEST/.venv/bin/hermes"
echo "export HERMES_BIN=$DEST/.venv/bin/hermes"
