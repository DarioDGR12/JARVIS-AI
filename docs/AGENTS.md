# Agentes Iron Man — rondas

Nueve agentes. Cada ronda investiga, corta un slice usable y pasa QA.  
**No** YOLO en el árbol (AGPL). **No** `Memory()` default (OpenAI + PostHog).

| ID | Frente | Ronda 1 | Ronda 2 | Ronda 3 | Ronda 4 |
|---|---|---|---|---|---|
| A-VOICE | Wake + STT + barge-in | Contrato + API. Sin modelos. | Mic HUD + Web Speech + barge-in | openWakeWord + faster-whisper (extras) + PCM | PCM HUD→`/ws/voice` si local + install script |
| A-VISOR | Overlay always-on-top | Visor compacto + Tauri `set_always_on_top` | Click-through (`set_ignore_cursor_events`) | Transparente + hit-test por región | Segunda ventana overlay (anillo) |
| A-SIGHT | Pantalla → Hermes | `explica la pantalla` hace handoff con OCR | Abrir URLs del OCR (Howdy) | — | Regiones OCR + «clica en …» (Howdy) |
| A-OFFICER | Watchdog proactivo | Load/RAM/temp + cooldown + toasts | Hermes caído + hablar alertas | — | Horas quietas + perfil desk/server |
| A-PRESENCE | Presencia webcam | Luma del frame → `hud.presence` | Standby al irte (sin apagar cam) | — | Welcome al volver |
| A-TOWER | Torre HA | «cómo está la casa» + entidades por dominio | «escena noche» + Howdy | — | Esquema de zonas |
| A-MEM | Memoria | `recuerda que` / `olvida` sobre JSONL | «qué recuerdas» lista hechos | mem0 OSS (Qdrant + Ollama, telemetría off) | Ranking léxico sin Ollama |
| A-BRIEF | Briefing globo | Extracto SENTINEL + Tierra NASA | Clima Open-Meteo (offline = skip) | Un HLS vivo (NASA TV / ISS) | 2 feeds + «otro feed» |
| A-DOOR | Puerta | Ingest de alerta. Armar pide Howdy. | Protocolo detector + script + HUD | Hijo JSONL fuera del repo | Plantilla + contrato `docs/DETECT.md` |

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

---

## Ronda 3 — resultados

### A-VOICE
**Investiga:** openWakeWord + faster-whisper pesan. Esta VM no tiene mic. El HUD ya oye con Web Speech.  
**Slice:** `LocalVoiceEngine` carga OWW/`hey_jarvis` + whisper `tiny` si el extra `[stt]` está. PCM por `/ws/voice` y `POST /api/voice/pcm`. Sin paquetes, el HUD sigue.  
**Siguiente:** bajar los modelos en Pop!_OS (`pip install '.[stt]'`).

### A-VISOR
**Investiga:** ignore de ventana entera no permite chrome. Hay que leer el cursor en nativo.  
**Slice:** visor transparente (`set_background_color` + CSS). Hilo Rust: titlebar/lado = clics; anillo = atraviesa.  
**Siguiente:** segunda ventana solo overlay.

### A-MEM
**Investiga:** `Memory()` default = OpenAI + PostHog.  
**Slice:** `Memory.from_config` con Qdrant on-disk + Ollama `nomic-embed-text` / `llama3.1:8b`. `MEM0_TELEMETRY=false`. `LayeredMemory` = JSONL + mem0. Sin Ollama, solo JSONL.  
**Siguiente:** embeddings locales si no hay Ollama.

### A-BRIEF
**Investiga:** Un HLS, no 10k cams. El master de NASA TV (`ntv1…/NASA-NTV1-HLS`) sigue en 200 pero las variantes dan 404 (playlist cacheada de 2024). Chrome a Akamai = 403 por `Origin`.  
**Slice:** pin `iss` → NASA+ VOD (`nasaplus.akamaized.net/output/16995.m3u8`, Far Out). `hls.js` 1.5.20. Proxy allowlist `*.akamaized.net` reescribe playlists. «pon el feed vivo» / clic en el pin.  
**Siguiente:** más de un directo (sigue capado). 24/7 cuando NASA+ vuelva a publicar HLS vivo.

### A-DOOR
**Investiga:** ultralytics es AGPL.  
**Slice:** `DetectorChild` habla JSONL con `$JARVIS_YOLO_DETECT`. Stub de protocolo en `brain/scripts/detect_stub.py` (sin YOLO). Al armar, loop + debounce.  
**Siguiente:** tu `detect.py` con YOLO26n fuera del repo.

---

## Ronda 4 — resultados

### A-VOICE
**Investiga:** Los extras `[stt]` no están en esta VM. El HUD no mandaba PCM.  
**Slice:** si `local.loaded`, Mic abre `/ws/voice` (s16le 16 kHz). Si no, Web Speech. «instala la voz» + `scripts/install_stt.sh`.  
**Siguiente:** modelos en Pop!_OS.

### A-VISOR
**Investiga:** visor = misma ventana compacta. Falta overlay solo anillo.  
**Slice:** ventana Tauri `overlay` (280², transparente, click-through). «pon el overlay» / botón Overlay.  
**Siguiente:** arrastrar el overlay.

### A-SIGHT
**Investiga:** OCR sin cajas. Highlight era un marco fijo.  
**Slice:** Tesseract TSV o tokens del texto → `regions[]`. «clica en …» + `POST /api/vision/click` (Howdy). xdotool solo si `JARVIS_VISION_CLICK=1`.  
**Siguiente:** teclado en región.

### A-OFFICER
**Investiga:** Hablaba a cualquier hora.  
**Slice:** `JARVIS_WATCH_QUIET=23:00-07:00` silencia TTS (toasts siguen). `JARVIS_PROFILE=desk|server`.  
**Siguiente:** no hablar si el puesto está vacío.

### A-PRESENCE
**Investiga:** Volver no saludaba. Howdy al mirar sin enrolar = 403 inútil.  
**Slice:** absent→present → toast «Bienvenido · piloto de vuelta».  
**Siguiente:** Howdy warm si hay compare.py.

### A-TOWER
**Investiga:** Casa era lista por dominio.  
**Slice:** `GET /api/ha/schematic` + grid de zonas. «mapa de la casa».  
**Siguiente:** planos por habitación.

### A-MEM
**Investiga:** Sin Ollama, search = substring.  
**Slice:** n-gramas + tokens. `backend=jsonl+lexical`. Sigue sin `Memory()`.  
**Siguiente:** fastembed ONNX opcional.

### A-BRIEF
**Investiga:** Un solo HLS.  
**Slice:** pin `jwst` (Cosmic Dawn). Cap 2. «otro feed» rota.  
**Siguiente:** 24/7 si NASA+ publica vivo.

### A-DOOR
**Investiga:** El stub no documentaba el contrato.  
**Slice:** `docs/DETECT.md` + `detect_template.py`. Snapshot `contract`. `POST /api/surveillance/tick`.  
**Siguiente:** tu YOLO26n fuera del repo.
