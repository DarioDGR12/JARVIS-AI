#!/usr/bin/env bash
# Official rhasspy/piper binary + one Spanish voice (MIT). Not novik133.
set -euo pipefail
DEST="${JARVIS_PIPER_HOME:-$HOME/.local/share/jarvis/piper}"
VOICE_ID="${JARVIS_PIPER_VOICE:-es_ES-davefx-medium}"
mkdir -p "$DEST/voices"
cd "$DEST"
if [[ ! -x "$DEST/piper/piper" ]]; then
  curl -fL --retry 4 --retry-delay 4 -o piper_linux_x86_64.tar.gz \
    https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
  tar -xzf piper_linux_x86_64.tar.gz
fi
ONNX="$DEST/voices/${VOICE_ID}.onnx"
if [[ ! -f "$ONNX" ]]; then
  # es_ES-davefx-medium → es/es_ES/davefx/medium/
  lang="${VOICE_ID%%-*}"            # es_ES
  rest="${VOICE_ID#*-}"             # davefx-medium
  speaker="${rest%-*}"              # davefx
  quality="${rest##*-}"             # medium
  iso="${lang%%_*}"                 # es
  base="https://huggingface.co/rhasspy/piper-voices/resolve/main/${iso}/${lang}/${speaker}/${quality}/${VOICE_ID}"
  curl -fL --retry 4 --retry-delay 4 -o "$ONNX" "${base}.onnx"
  curl -fL --retry 4 --retry-delay 4 -o "${ONNX}.json" "${base}.onnx.json"
fi
export JARVIS_PIPER_BIN="$DEST/piper/piper"
export JARVIS_PIPER_MODEL="$ONNX"
export JARVIS_PIPER_ESPEAK="$DEST/piper/espeak-ng-data"
echo "JARVIS_PIPER_BIN=$JARVIS_PIPER_BIN"
echo "JARVIS_PIPER_MODEL=$JARVIS_PIPER_MODEL"
echo "JARVIS_PIPER_ESPEAK=$JARVIS_PIPER_ESPEAK"
