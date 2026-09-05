#!/bin/sh
# Pop!_OS local wake + STT. Does not download YOLO. Does not call OpenAI.
#   cd brain && ./scripts/install_stt.sh
set -eu
cd "$(dirname "$0")/.."
python3 -m pip install -e '.[stt]'
echo "Modelos: openWakeWord hey_jarvis + faster-whisper tiny (JARVIS_WHISPER_MODEL)."
echo "Sin mic, el HUD sigue en Web Speech."
