# Agentes Iron Man — rondas

Nueve agentes. Cada ronda investiga, corta un slice usable y pasa QA.  
**No** YOLO en el árbol (AGPL). **No** `Memory()` default (OpenAI + PostHog).

| ID | Frente | Ronda 1 | Ronda 2 |
|---|---|---|---|
| A-VOICE | Wake + STT + barge-in | Contrato + API. Sin modelos. | Mic HUD + Web Speech + barge-in |
| A-VISOR | Overlay always-on-top | Visor compacto + Tauri `set_always_on_top` | Click-through (`set_ignore_cursor_events`) |
| A-SIGHT | Pantalla → Hermes | `explica la pantalla` hace handoff con OCR | Abrir URLs del OCR (Howdy) |
| A-OFFICER | Watchdog proactivo | Load/RAM/temp + cooldown + toasts | Hermes caído + hablar alertas |
| A-PRESENCE | Presencia webcam | Luma del frame → `hud.presence` | Standby al irte (sin apagar cam) |
| A-TOWER | Torre HA | «cómo está la casa» + entidades por dominio | «escena noche» + Howdy |
| A-MEM | Memoria | `recuerda que` / `olvida` sobre JSONL | «qué recuerdas» lista hechos |
| A-BRIEF | Briefing globo | Extracto SENTINEL + Tierra NASA | Clima Open-Meteo (offline = skip) |
| A-DOOR | Puerta | Ingest de alerta. Armar pide Howdy. | Protocolo detector + script + HUD |

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
**Investiga:** El globo enfoca pines. No habla. Feeds = extracto offline. Los continentes eran óvalos.  
**Slice:** «briefing» / «qué pasa en Tokio» → texto + mapa. Tierra NASA Blue Marble (3D y fallback 2D).  
**Siguiente:** clima / un feed vivo. Los otros 8 agentes de ronda 1 siguen.

### A-DOOR
**Investiga:** `surveillance.arm` ya era sensible. No había servicio. YOLO AGPL no se embebe.  
**Slice:** `GET/POST /api/surveillance/*`. Alertas externas → toast. Armar = 403 sin Howdy.  
**Siguiente:** proceso hijo YOLO fuera del repo.

**Tests ronda 1:** 95 passed.

---

## Ronda 2 — resultados

### A-VOICE
**Investiga:** Cargar openWakeWord + faster-whisper en esta VM (sin mic real) no da un producto. Chrome/WebKit sí tienen Web Speech.  
**Slice:** `GET /api/voice` (`wake=hud-phrase`, `stt=web-speech`, `barge_in=true`). Botón Mic. «jarvis …» → wake + transcript. Hablar corta el WAV.  
**Siguiente:** openWakeWord `hey_jarvis` + whisper local.

### A-VISOR
**Investiga:** Click-through es de ventana entera. Si está on, el ratón no recupera el HUD.  
**Slice:** `set_click_through` + permiso Tauri. Frase «deja pasar los clics» / «captura los clics». Bandeja «Mostrar» quita ignore.  
**Siguiente:** segunda ventana transparente / hit-test por región.

### A-SIGHT
**Investiga:** El OCR a veces trae URLs. Abrirlas es `xdg-open` = `shell`.  
**Slice:** «abre el enlace» + `POST /api/vision/open`. Howdy `vision.open`. Solo http(s).  
**Siguiente:** clic/teclado en regiones.

### A-OFFICER
**Investiga:** Hermes caído se veía solo en el titlebar.  
**Slice:** `officer_tick` ping + cooldown. Alertas se hablan si hay TTS y el turno está libre.  
**Siguiente:** umbrales por perfil / no hablar de noche.

### A-PRESENCE
**Investiga:** Irse no cambiaba el anillo. Apagar la cam al irte rompe Howdy.  
**Slice:** `present=false` → standby + toast + anillo apagado. La webcam sigue.  
**Siguiente:** Howdy al mirar.

### A-TOWER
**Investiga:** Escenas HA = `scene.turn_on`. Write sensible.  
**Slice:** «escena noche» → `scene.noche`. Howdy. Botón activar en Casa.  
**Siguiente:** schematic.

### A-MEM
**Investiga:** Los hechos existían; nadie los listaba.  
**Slice:** «qué recuerdas» / `GET /api/memory?facts=1`. Sigue sin `Memory()`.  
**Siguiente:** mem0 OSS (Qdrant + Ollama, telemetría off).

### A-BRIEF
**Investiga:** Open-Meteo no pide key.  
**Slice:** briefing de sitio + una línea de clima. Si la red falla, el extracto offline sigue.  
**Siguiente:** un feed vivo.

### A-DOOR
**Investiga:** Los detectores externos no tenían contrato.  
**Slice:** snapshot `ingest` + `fields`. `brain/scripts/surv_ingest.py`. Botón armar (Howdy).  
**Siguiente:** proceso hijo YOLO fuera del repo.
