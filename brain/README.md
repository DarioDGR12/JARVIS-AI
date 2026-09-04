# jarvis-brain

Cerebro del monorepo. Fase 1: **bus de eventos + Hermes + turno de texto**.

## Turno de texto (Fase 1)

Escribe en la terminal; Hermes responde. El overlay `instructions` (token `JARVIS_PHASE1_OK`) se inyecta en cada `POST /api/sessions/{id}/chat/stream`.

Hermes exige `API_SERVER_KEY` de **al menos 16 caracteres**. Si la clave es más corta, el gateway arranca pero **no** abre `:8642`.

```bash
# deps
cd brain
python -m pip install -e ".[dev]"

# tests unitarios
pytest

# stack local: mock LLM (:18765) + Hermes API (:8642)
# requiere Hermes instalado, p.ej. en /tmp/hermes-agent-src
bash scripts/run_phase1_stack.sh

# un turno
export API_SERVER_KEY=jarvis-phase1-key
export JARVIS_HERMES_URL=http://127.0.0.1:8642
python -m jarvis_brain chat -m "hola"

# o interactivo
python -m jarvis_brain chat

# QA obligatorio (stack + turno + evidencia)
bash scripts/qa_phase1.sh
```

Éxito = la respuesta contiene `JARVIS_PHASE1_OK` y el mock LLM reporta `overlay_seen: true`.

Bus: `ws://0.0.0.0:8765/ws/bus` y `POST /api/bus` (host/puerto vía `JARVIS_BUS_HOST` / `PORT` / `JARVIS_BUS_PORT`).

## TTS (siguiente fase — no usar ahora)

Default: RealtimeTTS + Chatterbox (GPU). Fallback: Piper.  
**ElevenLabs / OpenAI TTS / Edge no se instalan ni se usan como fallback.**
