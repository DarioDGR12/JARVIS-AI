#!/usr/bin/env bash
# First-time model pull. After this, run with HF_HUB_OFFLINE=1.
set -euo pipefail
DEST="${1:-/var/lib/jarvis/models/chatterbox-turbo}"
mkdir -p "$DEST"
huggingface-cli download ResembleAI/chatterbox-turbo \
  --include "*.safetensors" --include "*.json" --include "*.txt" --include "*.pt" --include "*.model" \
  --local-dir "$DEST"
python -m nltk.downloader -d "${NLTK_DATA:-/var/lib/jarvis/nltk_data}" punkt
echo "Offline path: export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 JARVIS_CHATTERBOX_PATH=$DEST"
