# JARVIS-AI

Asistente personal estilo Iron Man: BYOK + system prompt, orquestado en Pop!_OS.

**Estado:** Fase 1 del cerebro en `brain/` — bus WS + Hermes + turno de texto.

Lee [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md) antes de tocar nada. Ahí está qué repos se reutilizan, cuál es el cerebro, el contrato de eventos y la estructura del monorepo.

```bash
cd brain && python3 -m pip install -e ".[dev]" && pytest
bash brain/scripts/qa_phase1.sh   # turno de texto contra Hermes
bash brain/scripts/qa_phase2.sh   # TTS local (Piper) + WAV
```

Licencia del repo: Apache-2.0.
