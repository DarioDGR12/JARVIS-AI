# Agentes Iron Man — rondas

Nueve agentes. Cada ronda investiga, corta un slice usable y pasa QA.  
**No** YOLO en el árbol (AGPL). **No** `Memory()` default (OpenAI + PostHog).

| ID | Frente | Ronda 1 |
|---|---|---|
| A-VOICE | Wake + STT + barge-in | Contrato + API. Sin modelos. |
| A-VISOR | Overlay always-on-top | Visor compacto + Tauri `set_always_on_top` |
| A-SIGHT | Pantalla → Hermes | `explica la pantalla` hace handoff con OCR |
| A-OFFICER | Watchdog proactivo | Load/RAM/temp + cooldown + toasts |
| A-PRESENCE | Presencia webcam | Luma del frame → `hud.presence` |
| A-TOWER | Torre HA | «cómo está la casa» + entidades por dominio |
| A-MEM | Memoria | `recuerda que` / `olvida` sobre JSONL |
| A-BRIEF | Briefing globo | Extracto SENTINEL, no live |
| A-DOOR | Puerta | Ingest de alerta. Armar pide Howdy. |

---

## Ronda 1 — resultados

### A-VOICE
**Investiga:** El PCM de salida ya va por `/ws/voice`. No hay mic in, ni openWakeWord, ni faster-whisper en el árbol. Cargarlos en esta VM (CPU, sin mic) no da un producto.  
**Slice:** `GET /api/voice` (`wake=stub`, `stt=stub`). `POST /api/voice/wake` → `listening`. `POST /api/voice/transcript` → el mismo turno que el chat.  
**Siguiente:** openWakeWord `hey_jarvis` + whisper local + barge-in.

### A-VISOR
**Investiga:** Una sola ventana Tauri 1040×700. Falta `always_on_top`.  
**Slice:** frase «pon el visor» / botón Visor. CSS compacto (solo Inicio). Comando Rust `set_visor` (always-on-top + 440×560).  
**Siguiente:** click-through, segunda ventana transparente.

### A-SIGHT
**Investiga:** Captura existe; no entraba a Hermes. `hud.highlight` se guardaba y no se pintaba.  
**Slice:** «explica la pantalla» captura, mete contexto en Hermes, resalta el preview. «qué hay en pantalla» sigue siendo captura local.  
**Siguiente:** clic/teclado detrás de Howdy.

### A-OFFICER
**Investiga:** Stats `/proc` solo a demanda.  
**Slice:** `Watchdog` cada 20 s. Umbrales `JARVIS_WATCH_*`. Cooldown 120 s. Alertas → toast + anillo `alert`.  
**Siguiente:** hablar solo si importa + Hermes caído.

### A-PRESENCE
**Investiga:** Webcam HUD ya es un stream. MediaPipe no está.  
**Slice:** cada 2.5 s, luma 32×24. Si cambia, `POST /api/hud/presence`. Titlebar `piloto` / `vacío`.  
**Siguiente:** standby al irte; Howdy al mirar.

### A-TOWER
**Investiga:** Casa era una lista plana.  
**Slice:** agrupado por dominio. «cómo está la casa» (config / ping / luces). Escenas Howdy = ronda 2.  
**Siguiente:** schematic + escenas.

### A-MEM
**Investiga:** JSONL + `overlay_block` ya existían. Nadie decía «recuerda». `Memory()` sigue prohibido.  
**Slice:** «recuerda que …» / «olvida …». Hechos con `role=fact`.  
**Siguiente:** mem0 OSS (Qdrant + Ollama, telemetría off).

### A-BRIEF
**Investiga:** El globo enfoca pines. No habla. Feeds = extracto offline.  
**Slice:** «briefing» / «qué pasa en Tokio» → texto del extracto + abre Mapa.  
**Siguiente:** clima / un feed vivo.

### A-DOOR
**Investiga:** `surveillance.arm` ya era sensible. No había servicio. YOLO AGPL no se embebe.  
**Slice:** `GET/POST /api/surveillance/*`. Alertas externas → toast. Armar = 403 sin Howdy.  
**Siguiente:** proceso hijo YOLO fuera del repo.

**Tests ronda 1:** 95 passed.
