# jarvis-brain

Cerebro del monorepo. Este directorio empieza por la **voz local**.

## TTS (100% local)

Default: RealtimeTTS + Chatterbox (GPU). Fallback: Piper (binario del sistema).  
**ElevenLabs / OpenAI TTS / Edge no se instalan ni se usan como fallback.**

```bash
# deps de la capa (torch + chatterbox). Primera vez baja ~3–4 GB de pesos HF.
uv pip install -e ".[tts,dev]"

# Prefetch para correr offline después:
#   huggingface-cli download ResembleAI/chatterbox-turbo --local-dir /var/lib/jarvis/models/chatterbox-turbo
#   export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

pytest
```

Dos voces = dos WAV ≥ 5 s (`JARVIS_VOICE_JARVIS`, `JARVIS_VOICE_COMPANION`). No se clona al usuario.

En una RTX 4060 8 GB: Hermes 7B Q4 + Chatterbox Turbo **no caben**. Usar LLM ≤4B Q4 + Nano, o Chatterbox/Piper en CPU. YOLO del Agente 6 en CPU.
