# Plan de integración JARVIS-AI

**Estado:** propuesta — no hay implementación todavía.  
**Fecha:** 2026-09-04  
**Repo:** [DarioDGR12/JARVIS-AI](https://github.com/DarioDGR12/JARVIS-AI) (licencia Apache-2.0)  
**Plataforma objetivo:** Pop!_OS (COSMIC / GNOME, Linux, Wayland)  
**Enfoque:** BYOK + system prompt. No se entrena ningún modelo. Se orquesta.

Este documento es el entregable de cinco agentes especializados más un coordinador.  
**No copies código** de repos sin licencia o GPL al árbol. Ver [§7 Licencias](#7-licencias-qué-se-puede-copiar).

---

## 0. Decisión ejecutiva (lo que hay que aprobar)

| Pregunta | Respuesta |
|---|---|
| Cerebro principal | **eadmin2/jarvis_ai** (`VoicePipelineServer` + `HermesAPI`) + **Hermes Agent** como motor LLM/memoria/tools |
| Qué aporta novik133/jarvis | Solo **ideas** (wake word, Piper TTS, phrase-map, stats `/proc`). **No** el proceso C++/QML. **No** copiar código (GPL-3.0) |
| HUD | **Reimplementar** estética Iron Man. jarvis-hud **no tiene LICENSE** — no se puede copiar |
| Globo | **sentinel-feed-grid** como vista `map` **dentro del HUD** (iframe same-origin, Fase 1). WebcamMap = **solo dataset** OSM |
| Visión de pantalla | **Arquitectura** de OpenMagicPointer (MIT). Captura real en Pop!_OS = **xdg-desktop-portal** (trabajo nuevo). ProjectMidas = idea de OCR local, **sin licencia** |
| Domótica | Home Assistant **fuera** del monorepo. Cliente LAN: Long-Lived Token + REST + WebSocket |
| Personalidad | Un modelo, dos overlays. IDs en código: `jarvis` / `companion` (no usar “Cortana” como identificador) |
| Transporte | WebSocket JSON `ws://127.0.0.1:<port>/ws/bus` + canal de voz PCM aparte |

Si esto te encaja, el siguiente paso (cuando lo apruebes) es Fase 1: bus de eventos + cerebro + Hermes, sin HUD todavía.

---

## 1. Resumen de cada repo

Fuentes: `gh repo view` / `gh api` el 2026-09-04 + clones shallow en `/tmp/agentN-repos/` + lectura de código. Stats de issues: GitHub cuenta PRs dentro de `open_issues`.

### 1.1 novik133/jarvis — voz local KDE (NO cerebro)

| Campo | Valor |
|---|---|
| URL | https://github.com/novik133/jarvis |
| Stack | **C++ / QML / CMake** — Qt 6 + **KDE Plasma 6 plasmoid** |
| LLM | `POST {llmServerUrl}/v1/chat/completions` a llama.cpp local. **Sin API key** |
| Voz | whisper.cpp (wake + STT), Piper TTS, Qt Multimedia |
| Memoria | Historial en RAM (se pierde al reiniciar Plasma) |
| Licencia | **GPL-3.0** (`metadata.json` + LICENSE) |
| Último push | 2026-03-28 (~5 meses) |
| Stars / issues | 20 / 3 |
| Encaje Pop!_OS | **No corre nativo.** Pop!_OS no es Plasma 6 |

**Sirve:** ideas de wake word CPU, Piper por oraciones, mapa frase→comando (volumen, lock) *antes* del LLM, inyección de CPU/RAM/temp en el prompt, saludo por franja horaria.

**No sirve:** el plasmoid entero, llama-server como cerebro (anti-BYOK), parser `[ACTION:]` que ejecuta shell sin allowlist, HUD QML.

**Riesgo:** copiar C++/QML GPL-3 **contamina** un derivado que quieras vender como guía + código.

### 1.2 eadmin2/jarvis_ai — orquestador de voz (SÍ cerebro)

| Campo | Valor |
|---|---|
| URL | https://github.com/eadmin2/jarvis_ai |
| Stack | **Python** FastAPI + uvicorn + WebSocket; HUD HTML vanilla; plugins Hermes |
| LLM | Hermes Agent Sessions API (`POST /api/sessions/{id}/chat/stream`). Fallback Anthropic-only |
| Voz | faster-whisper / RealtimeSTT; TTS **ElevenLabs** en `main`; wake word **openWakeWord** en `client/` (documentado como client Windows→server Mac) |
| Memoria | Sesiones Hermes + `session_key`; MEMORY.md / USER.md / SOUL.md (lado Hermes) |
| Licencia | **MIT** |
| Último push a `main` | 2026-06-13 (joven; issue #4 de agosto 2026 con systemd/Kokoro **no mergeado**) |
| Stars / issues | 148 / 2 |
| Encaje Pop!_OS | Python + systemd es viable. `main` está pensado para macOS (launchd). Linux “should work” |

**Sirve:** `VoicePipelineServer`, `HermesAPI`, protocolo WS de turno, `/api/summon` → HUD, plugin `hud_display`, STT local, barge-in, approvals ALLOW/DENY, redacción de secretos.

**No sirve como UI final:** el `index.html` holográfico (el HUD lo arma el Agente 2). ElevenLabs como TTS único. launchd. Fallback Anthropic-only. `hermes.instructions` en yaml **no se envía** en `main`.

**Hermes Agent** ([NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), MIT, push 2026-09-04) es el *motor* de razonamiento (BYOK, tools, memoria). eadmin2 es la *capa de orquestación*. El producto necesita las dos.

### 1.3 MuhammadFahru/jarvis-hud — prototipo visual (reimplementar)

| Campo | Valor |
|---|---|
| URL | https://github.com/MuhammadFahru/jarvis-hud |
| Stack | HTML/CSS/JS estático. **Sin `package.json`.** Three.js **r128** + MediaPipe Hands/Face Mesh por CDN |
| Gestos reales | Solo **pinch** (1 mano, umbral `d<0.05`) y **spread** (2 manos). No click, no swipe, no handedness |
| Licencia | **Ninguna** (all rights reserved por defecto) |
| Último push | 2025-11-20 — **1 commit**, 0 stars |
| Encaje | Idea de overlay (video + canvas 3D + chrome 2D). El “globo” es un icosaedro MCU, no un módulo |

**Sirve:** estética (cian, Orbitron, scanlines, capas overlay), idea de pinch/spread.

**No sirve:** métricas/terminal fake (`Math.random()`), globo MCU acoplado a gestos, CDNs sin pin, `pointer-events: none` (el HUD no es clicable), cero bus de eventos.

**Legal:** un JARVIS OSS **no puede copiar** `app.js` / `styles.css`. Se reimplementa la estética.

### 1.4 movingdevious/sentinel-feed-grid — globo 3D real (módulo HUD)

| Campo | Valor |
|---|---|
| URL | https://github.com/movingdevious/sentinel-feed-grid |
| Stack | **Un HTML** + Three.js r128 + hls.js. Globo 3D **real** (esfera, textura Blue Marble, fronteras, markers). **No Cesium** |
| Feeds | ~41 YouTube/HLS embebidos + Caltrans/TfL snapshots + pines click-through. `feeds.json` del repo son **placeholders** |
| API | `window.SENTINEL.addFeeds/loadSet/...`. `focusLatLon` **existe por dentro** pero no está exportado. **No hay `postMessage`** |
| Licencia | **MIT** (`LICENSE` + `package.json`). El README dice “Proprietary” — prevalece el SPDX MIT |
| Último push | 2026-08-16 — 1 star, repo joven |
| Local | **No.** Textura, fronteras, YT, DOT, ISS, etc. piden red |

**Sirve:** el globo + schema de feeds `{id,loc,country,lat,lon,yt\|hls\|img}` + capas opcionales.

**No sirve como app aparte:** su chrome táctico pisa el HUD si se monta en el mismo document.

### 1.5 wvanderp/WebcamMap — dataset extra (no UI)

| Campo | Valor |
|---|---|
| URL | https://github.com/wvanderp/WebcamMap |
| Stack | React 19 + Vite + **Leaflet 2D** (no globo). Datos: `data/webcams.json` (~9 740 cams, ~8.4 MB) |
| Runtime | El browser **no** llama Overpass. El JSON va embebido. Preview de stream = **no implementado** |
| Licencia | Código **MIT**. Datos **ODbL** (OSM — atribución + share-alike) |
| Último push | 2026-09-03 (cron de datos). Último commit humano 2026-04-12 |
| Stars / issues | 9 / 6 (varios Dependabot) |

**Sirve:** data layer. Adaptar `yt` / `hls` / `img` y **no** volcar 10k sprites (SENTINEL aguanta cientos).

**No sirve:** la app React/Leaflet dentro del HUD.

### 1.6 mengzili/openmagicpointer — diseño de captura (no binario)

| Campo | Valor |
|---|---|
| URL | https://github.com/mengzili/openmagicpointer |
| Stack | Electron 32 + TypeScript. Captura `desktopCapturer`, idle `uiohook-napi`, VLM BYOK |
| Qué hace | Hints ≤140 chars cerca del cursor. **No** OCR, **no** bboxes, **no** computer-use |
| Licencia | **MIT** |
| Último push | 2026-05-20 (un día de commits). 2 stars |
| Linux | README: “Windows-tested”. Paridad macOS/Linux = **roadmap, no hecha**. CI solo `windows-latest` |

**Sirve:** downscale ≤1280, fingerprint perceptual (no llamar al LLM si la pantalla no cambió), throttle/idle, BYOK VLM, defaults de privacidad documentados.

### 1.7 pkante/ProjectMidas — idea OCR (no copiar)

| Campo | Valor |
|---|---|
| URL | https://github.com/pkante/ProjectMidas |
| Stack | Electron 28 + Python: Tesseract cada 10s → embeddings OpenAI → ChromaDB → GPT-4o |
| Licencia | **Ninguna** |
| Último push | 2025-07-23. 0 stars |
| Linux | Menciona `apt install tesseract-ocr`. Permisos de captura documentados **solo en macOS**. Cero Wayland/PipeWire |

**Sirve:** idea “OCR local → texto al cerebro”. Botón share-screen = `vision.capture once`.

**No sirve:** embeddings cloud cada 10s, OCR on `app.ready()`, código sin licencia.

### 1.8 home-assistant/core — hub externo (no monorepo)

| Campo | Valor |
|---|---|
| URL | https://github.com/home-assistant/core |
| Stack | Python, Apache-2.0 |
| Último push | 2026-09-04 (muy vivo). ~90k stars |
| Rol | El usuario corre HAOS o Container. JARVIS es cliente LAN |

APIs oficiales (verificadas):

- REST: https://developers.home-assistant.io/docs/api/rest/
- WebSocket: https://developers.home-assistant.io/docs/api/websocket/
- Auth / long-lived token: https://developers.home-assistant.io/docs/auth_api/

Control = `POST /api/services/{domain}/{service}`. **Nunca** `POST /api/states` (no habla con el dispositivo).

---

## 2. Cerebro principal vs módulos sueltos

```
                    ┌─────────────────────────────────────┐
                    │  CEREBRO (adaptación de eadmin2)    │
                    │  event bus · turno de voz · persona │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  Hermes Agent (deps, MIT, BYOK)     │
                    │  SOUL.md · MEMORY.md · tools        │
                    └──────────────┬──────────────────────┘
           ┌───────────┬───────────┼───────────┬──────────┐
           ▼           ▼           ▼           ▼          ▼
         HUD         Globo      Visión       HA        Voz local
        (nuevo)    (SENTINEL   (portal      (LAN      openWakeWord
                    iframe)     + OCR)      token)    Piper (idea)
```

**Por qué no novik133 como cerebro**

1. Exige Plasma 6 — Pop!_OS no lo es.  
2. No hay bus de eventos ni tools.  
3. No es BYOK (llama.cpp local, sin auth).  
4. GPL-3.0 vs guía vendible + Apache-2.0 del monorepo.  
5. Memoria no persistente.

**Por qué no “Hermes solo”**

Hermes no trae STT/TTS, wake word, HUD ni bus para mapa/HA/visión. eadmin2 ya resuelve el turno de voz y el precedente `/api/summon`.

**Módulos sueltos a reimplementar (ideas de novik133, código nuevo MIT/Apache):**

- Wake word: preferir **openWakeWord** (`hey_jarvis`) del client de eadmin2; whisper-substring de novik133 solo como fallback CPU.  
- TTS default Linux: **Piper** (local, $0). ElevenLabs = provider opcional BYOK. Kokoro (issue #4, no en `main`) = candidato 2.  
- Phrase-map: “sube volumen / bloquea sesión” **antes** de Hermes.  
- `system.stats` desde `/proc`.

---

## 3. Estructura de monorepo

Cada pieza tiene **su propio** `pyproject.toml` / `package.json`. El cerebro es el único que habla con el LLM. Nadie más llama a OpenAI/Anthropic/OpenRouter.

```
JARVIS-AI/                          # Apache-2.0 (ya en el repo)
├── docs/
│   └── INTEGRATION_PLAN.md         # este archivo
├── schemas/
│   └── events/                     # JSON Schema del bus (fuente de verdad)
├── brain/                          # Python (uv) — orquestador
│   ├── src/jarvis_brain/
│   │   ├── bus/                    # WS /ws/bus + HTTP POST /api/bus
│   │   ├── hermes/                 # cliente Sessions API
│   │   ├── persona/                # clasificador + overlays
│   │   ├── voice/                  # STT / TTS / wake
│   │   └── tools/                  # plugins Hermes: hud, map, ha, vision
│   └── pyproject.toml
├── hud/                            # JS (Vite) — REIMPLEMENTADO
│   ├── src/
│   │   ├── chrome/                 # overlay 2D
│   │   ├── gestures/               # MediaPipe Hands
│   │   ├── views/                  # home | map | vision | ha | chat
│   │   └── bus.ts
│   └── package.json
├── vision/                         # Python — captura de pantalla
│   └── src/jarvis_vision/
├── adapters/
│   └── homeassistant/              # cliente REST + WS
├── vendor/
│   └── globe/                      # sentinel-feed-grid/src (MIT) + NOTICE
├── data/
│   └── webcams/                    # extracto yt|hls|img + NOTICE ODbL
├── prompts/
│   ├── SOUL.md
│   ├── persona-jarvis.md
│   └── persona-companion.md
├── deploy/
│   ├── systemd/                    # brain, hud-static, vision
│   └── docker-compose.ha.yml       # opcional: imagen oficial HA
├── scripts/
└── THIRD_PARTY_NOTICES.md
```

**Qué no entra nunca**

| Cosa | Por qué |
|---|---|
| Código de novik133 | GPL-3.0 |
| Código de jarvis-hud | Sin licencia |
| Código de ProjectMidas | Sin licencia |
| `home-assistant/core` | 876 MB, se corre aparte |
| App React de WebcamMap | Solo el JSON filtrado |
| Keys / `.env` | `HA_TOKEN`, keys LLM, ElevenLabs |

**Dependencias por paquete (no se pisan)**

| Paquete | Runtime | Habla con LLM | Habla con red externa |
|---|---|---|---|
| `brain` | Python 3.12 | Sí, **solo vía Hermes** | Hermes loopback + TTS opcional |
| `hud` | Chromium / Vite | No | CDN vendorado; cámara local |
| `vendor/globe` | iframe estático | No | YouTube, DOT, tiles de textura |
| `vision` | Python | No (el cerebro decide si hay VLM) | No, salvo que el cerebro pida VLM |
| `adapters/ha` | Python | No | Solo `HA_URL` LAN |

---

## 4. Contrato del bus (coordinado)

Los cinco agentes propusieron eventos. El coordinador **unificó** nombres y payloads. Esto es la fuente de verdad. Si un agente decía otra cosa, gana esta sección.

### 4.1 Envelope

```json
{
  "v": 1,
  "id": "01J7QK3...",
  "ts": "2026-09-04T05:35:00.123Z",
  "source": "brain|hud|map|vision|ha|voice|system",
  "type": "hud.display",
  "corr_id": null,
  "payload": {}
}
```

- `id`: ULID.  
- `corr_id`: id del evento al que se responde (`ha.result` cita `ha.command`).  
- `ts`: ISO-8601 UTC (no epoch).  
- Transporte de control: `ws://127.0.0.1:<port>/ws/bus` (JSON).  
- Transporte de voz: WS **aparte** (PCM int16), para no mezclar audio y control.  
- HTTP `POST /api/bus` para tools de Hermes (mismo envelope).

### 4.2 Correcciones respecto a los agentes

| Conflicto | Agente A | Agente B | Decisión |
|---|---|---|---|
| Envelope | A1: `v, source, corr_id, ts` ISO | A2: `{id,type,payload,ts}` epoch | **A1** |
| `hud.display` | A1: `media/src/title` (eadmin2) | A2: `type/content/duration` | Unión: `kind` + `content` + campos media opcionales. **No** usar `type` dentro del payload (choca con `envelope.type`) |
| `hud.set_mode` | A1: operacional + `persona` | A2: `{ visual: jarvis\|companion }` | Ambos: `operational` + `visual` |
| Vista del globo | A2: `view: "map"` | A3: `view: "globe"` | **`map`** (contrato original) |
| Gestos | A1 listó swipe/hold | A2: solo pinch/spread existen | **`pinch` \| `spread`** al inicio |
| `vision` timestamp | A1: `ts` | A4: `timestamp` epoch + `source` | Payload: `timestamp` epoch ms de la captura + `source: "screen"`. El `ts` del envelope es el del evento |
| Modo cálido | “cortana” en prosa | — | Código/eventos: **`companion`**. Prosa de producto: “modo compañero”. Evita marca Cortana en OSS |

### 4.3 HUD ↔ cerebro

**Cerebro → HUD**

| type | payload | Notas |
|---|---|---|
| `hud.display` | `{ kind: "text"\|"card"\|"alert"\|"toast"\|"log"\|"media", content, duration_ms?, media?, src?, title?, position? }` | Extiende `/api/summon` de eadmin2 |
| `hud.speak` | `{ text, viseme?, voice: "jarvis"\|"companion"\|"current", interrupt? }` | **Solo visual** (onda/anillo). El PCM va por el canal de voz |
| `hud.set_mode` | `{ operational: "standby"\|"listening"\|"thinking"\|"tool"\|"speaking"\|"alert"\|"boot", visual: "jarvis"\|"companion" }` | `visual` cambia CSS, no la personalidad |
| `hud.show_view` | `{ view: "home"\|"map"\|"vision"\|"ha"\|"chat", visible?: true }` | `map` monta el iframe SENTINEL |
| `hud.highlight` | `{ target, id?, bbox?, reason?, duration_ms? }` | Nuevo. Visión / HA / mapa |
| `persona.changed` | `{ from, to, reason[], confidence, hysteresis_s }` | HUD mapea `companion` → `visual: companion` |
| `brain.status` | `{ state, run_id?, tool?, preview? }` | Alias de `agent_status` de eadmin2 |
| `brain.approval_request` | `{ run_id, approval_id, data }` | Ya existe en eadmin2 |

**HUD → cerebro**

| type | payload | Notas |
|---|---|---|
| `hud.ready` | `{ views: ["home","map","vision","ha","chat"], camera: bool, viewport: {w,h} }` | Tras WS + `getUserMedia` resuelto (ok o fail) |
| `hud.gesture` | `{ name: "pinch"\|"spread", hand: "left"\|"right"\|"both", confidence, timestamp }` | Solo edges, no 30 fps de landmarks |
| `hud.click` | `{ target, id?, method: "gesture"\|"pointer" }` | **Hay que construirlo** (el demo tiene `pointer-events: none`) |
| `brain.approval_decision` | `{ run_id, approval_id, decision }` | Ya existe en eadmin2 |
| `brain.stop` | `{ run_id? }` | |

### 4.4 Mapa (módulo dentro del HUD)

El HUD hospeda. El cerebro **no** importa Three.js.

**Ciclo de vida (HUD)**

```
hud.show_view { view: "map" }
  → mapModule.mount(#view-slot)
      → crea iframe same-origin /globe/
      → espera map.ready
      → opcional: addFeeds(extracto WebcamMap)

hud.show_view { view: "home" }  (u otra)
  → mapModule.unmount()
      → iframe.remove()   // OBLIGATORIO: mata WebGL + decoders HLS
```

**Por qué iframe (Fase 1), no escena Three compartida**

SENTINEL y el HUD son **dos** `WebGLRenderer` + dos `requestAnimationFrame` + Three r128 vs Three moderno. Montar el HTML de SENTINEL en el mismo document pisa IDs (`#hud`, `#scene`). iframe aísla. Fase 2 (opcional): extraer el `Group` del globo a la escena del HUD.

**Cerebro → mapa** (HUD reenvía por `postMessage` al iframe)

| type | payload | Traducción SENTINEL |
|---|---|---|
| `map.focus` | `{ lat, lon, zoom? }` | `focusLatLon`. `zoom` se mapea a `tDist` (4.4–15); SENTINEL no tiene zoom tipo tiles |
| `map.show_feeds` | `{ region?, tags? }` | `curFilter` / chips / `loadSet` |
| `map.query` | `{ q }` | `buildDirectory(q)` — substring, **no geocoder**. Coords → usar `map.focus` |

**Mapa → cerebro**

| type | payload |
|---|---|
| `map.ready` | `{ source: "sentinel" }` |
| `map.selection` | `{ lat, lon, feed_id? }` |
| `map.feed_ready` | `{ count, region }` |
| `map.error` | `{ reason: "not_mounted"\|... }` |

`window.SENTINEL` hoy **no** exporta focus/query/onSelect. El bridge (parche mínimo en el iframe) los expone. El cerebro no conoce SENTINEL.

**WebcamMap:** adaptador host → `{ id, loc, country, lat, lon, yt|hls|img }`. Descartar `unavailable` / `invalidUrl` / `duplicate`. Cap por región. Atribución ODbL en `THIRD_PARTY_NOTICES.md`.

**Cámara:** una sola `getUserMedia`, dueño = HUD. El globo **no** abre otra cámara. Gestos de rotar/escalar el globo se consumen **dentro** del HUD (`ctx.gesture`); el cerebro recibe `hud.gesture` solo como telemetría.

### 4.5 Visión de pantalla ↔ cerebro

La webcam del HUD es **solo gestos**. “Qué hay en el mundo” = **pantalla**. `source` de este agente es siempre `"screen"`.

**Cerebro → visión**

| type | payload |
|---|---|
| `vision.capture` | `{ mode: "once"\|"region", display?: 0 }` |
| `vision.watch` | `{ enabled: bool, interval_ms }` — default `enabled: false`. Piso 5000 ms, default 15000 |

**Visión → cerebro**

```json
{
  "type": "vision.screen_context",
  "payload": {
    "text": "VS Code — main.py líneas 40-80",
    "ocr": "...",
    "regions": [],
    "timestamp": 1756964100123,
    "source": "screen",
    "image_ref": null
  }
}
```

- `regions` empieza **vacío** (ningún repo produce bboxes).  
- **No** mandar PNG al cerebro por defecto. Buffer = 1 frame en RAM.  
- `watch` + fingerprint (idea OMP): si la pantalla no cambió, no emitir.  
- VLM BYOK solo si el cerebro lo pide y hay key. OCR local (Tesseract) = default.

**Linux / Pop!_OS (deal-breaker):** ni OMP ni Midas están verificados en COSMIC/Wayland. `desktopCapturer` + Electron 28/32 + `uiohook` (X11) **fallará** en Wayland (picker del portal, 1 source, thumbs vacíos). Camino correcto:

1. Detectar `XDG_SESSION_TYPE`.  
2. `once` → D-Bus `org.freedesktop.portal.Screenshot`.  
3. `watch` → portal ScreenCast / PipeWire, **no** `getSources()` en loop.  
4. X11: fallback `desktopCapturer` / `maim`.  
5. Idle: **no** uiohook en Wayland.

**Privacidad (defaults más estrictos que ambos repos):** visión opt-in; watch off; no PNG a disco; no historial; kill switch + indicador “SCREEN VISION ON”; tratar `text`/`ocr` como untrusted (prompt injection visual).

**Computer-use (click/type):** **no existe** en estos repos y **no** entra en el MVP.

### 4.6 Home Assistant ↔ cerebro

HA corre aparte. El adaptador traduce eventos ↔ HTTP/WS.

**Cerebro → HA**

```json
{
  "type": "ha.command",
  "payload": {
    "domain": "light",
    "service": "turn_on",
    "entity_id": "light.living_room",
    "data": { "brightness": 180 }
  }
}
```

→ `POST {HA_URL}/api/services/{domain}/{service}` + `Authorization: Bearer {HA_TOKEN}`.

**HA → cerebro**

| type | payload |
|---|---|
| `ha.state` | `{ entity_id, state, attributes, ts }` — snapshot REST al arrancar + WS `state_changed` |
| `ha.result` | `{ ok, error, response }` + `corr_id` del command |

**Reglas**

- `domain`/`service` deben existir en `GET /api/services` de **esa** casa. El LLM descubre, no lleva catálogo fijo.  
- Denylist: `homeassistant.stop` / `restart` / `reload_*`.  
- Env: `HA_URL` (RFC1918 / localhost) + `HA_TOKEN`. Nunca en git ni en el prompt.  
- REST = verbos; WS = estados en vivo. v0 puede ser solo REST.  
- **100% local** solo si HA **y** los dispositivos están en LAN. Una bombilla Tuya-cloud no se vuelve local por usar la API de HA.  
- No iframe de HA en el HUD salvo opcional a `HA_URL` (sin token en la URL).  
- No forkar core, no custom_components, no Supervisor API.

### 4.7 Flujo de un turno

```
voice.wake | hud.click | hud.gesture
    → STT → voice.transcript
    → snapshot: vision.screen_context + ha.state + map.selection + system.stats + hora
    → phrase-map (volumen/lock) ──hit──► hud.speak corto, sin Hermes
    → PersonaClassifier → overlay jarvis|companion
    → Hermes chat/stream { input, instructions: overlay }
         ├ tool hud_*     → hud.display / hud.show_view / hud.highlight
         ├ tool map_*     → map.focus / map.show_feeds / map.query
         ├ tool ha_*      → ha.command
         └ tool vision_*  → vision.capture / vision.watch
    → assistant.delta → hud.speak + TTS PCM
    → persona.changed / hud.set_mode
```

Una sesión Hermes (`jarvis-main`). **No** dos sesiones (rompería la memoria).

---

## 5. Personalidad automática

No hay dos modelos. No hay toggle en el HUD. El clasificador vive en el cerebro, **antes** de Hermes.

**Identidad estable:** `prompts/SOUL.md` — quién es, que existen dos *registros de voz*, default JARVIS. No fanfic “Tony Stark”. El usuario pidió seco/neutral.

**Overlays por turno** (`persona-jarvis.md` / `persona-companion.md`): se inyectan como `instructions` / ephemeral system. **No** se reescribe `SOUL.md` mid-session.

| | `jarvis` (default) | `companion` |
|---|---|---|
| Tono | Seco, neutro, breve | Más cálido, un toque de cercanía |
| Longitud | 1–3 frases | 2–4 frases |
| Tools | Iguales | Iguales |
| TTS | voz A (Piper) | voz B opcional o mismos pesos + rate |

**Señales locales (sin segunda API cara)**

| Señal | → jarvis | → companion |
|---|---|---|
| Hora | 06:00–21:59 | 22:00–05:59, mañanas de fin de semana |
| Tipo | comando, sistema, HA, código | ánimo, saludo, personal |
| Racha | turnos cortos / tools | >2 turnos de charla sin tools |
| Pantalla | IDE, terminal | ocio / vacío |
| HA | away / alarma | home / noche / luces tenues |
| Texto | open, set, kill, deploy | thanks, good night, cómo estás |

**Histéresis:** cambiar solo si `confidence ≥ 0.65` y (180 s desde el último cambio **o** señal fuerte). Boot = `jarvis`. “Sé más formal / más cercano” es una señal más, no un modo permanente.

**NO VERIFICADO:** que `POST /api/sessions/{id}/chat/stream` acepte `instructions` en la Hermes que instalemos. Plan B: `HERMES_EPHEMERAL_SYSTEM_PROMPT` o Responses API. Elegir con un `curl` en Fase 1.

eadmin2 `main` **no** cablea `hermes.instructions`. Es el primer parche del cerebro.

---

## 6. Pop!_OS — runtime

| Pieza | Cómo corre |
|---|---|
| Hermes Agent | proceso local loopback (puerto típico 8642). Keys en `~/.hermes/.env` |
| brain | systemd user service, FastAPI, `0.0.0.0` solo si hace falta; preferir `127.0.0.1` |
| HUD | **Chromium kiosk** → `http://127.0.0.1:<port>/hud/`. Electron solo si hace falta overlay de escritorio |
| Globo | estáticos same-origin `/globe/` dentro del HUD |
| Visión | servicio Python + portal COSMIC/GNOME |
| HA | Docker `network_mode: host` en el mismo PC **o** HAOS en otra máquina. UI `:8123` |

Cámara: PipeWire + `xdg-desktop-portal`. Una sola app (el HUD) posee el device.

Audio: PipeWire. El client de wake word de eadmin2 hay que portar a Linux (issue #4 ya lo intentó en Ubuntu, no está en `main`).

---

## 7. Licencias: qué se puede copiar

El monorepo ya es **Apache-2.0**. Una guía de pago sobre código Apache/MIT es viable. Meter GPL o código sin licencia en el tarball **no**.

| Repo | Licencia | Acción |
|---|---|---|
| eadmin2/jarvis_ai | MIT | Adaptar con copyright notice |
| NousResearch/hermes-agent | MIT | Dependencia externa, no vendorizar el core |
| novik133/jarvis | GPL-3.0 | Ideas only |
| MuhammadFahru/jarvis-hud | **Ninguna** | Reimplementar |
| sentinel-feed-grid | MIT (README contradice) | Vendor `src/` + NOTICE |
| WebcamMap código | MIT | No hace falta la app |
| WebcamMap datos | **ODbL** | Extracto + atribución OSM + share-alike del dataset |
| openmagicpointer | MIT | Ideas + patrones; no el binario Windows |
| ProjectMidas | **Ninguna** | Ideas only |
| home-assistant/core | Apache-2.0 | Cliente nuevo; no fork |
| Three.js / hls.js | MIT / Apache-2.0 | Vendor pineado (no CDN `latest`) |

---

## 8. Fases (cuando apruebes — no ahora)

1. **Bus + cerebro + Hermes** en Pop!_OS. Cablear `instructions`. systemd. `requirements.lock`. Smoke: texto → Hermes → texto.  
2. **Voz local:** STT + Piper + openWakeWord. Phrase-map.  
3. **HUD reimplementado** + WS + gestos pinch/spread + `hud.ready`. Chromium kiosk.  
4. **Vista `map`:** vendor SENTINEL + bridge `postMessage` + adaptador WebcamMap (extracto).  
5. **HA adapter** + tool Hermes `ha_*` + discovery.  
6. **Visión:** portal Screenshot + OCR opt-in + fingerprint. Watch off por default.  
7. **PersonaClassifier** + overlays + `persona.changed`.  
8. Docs de la guía (setup Pop!_OS, BYOK, HA, avisos legales).

---

## 9. Riesgos abiertos (no esconder)

1. Hermes API drift (eadmin2 escrito contra v0.16; Hermes empuja a diario).  
2. `instructions` en session stream: NO VERIFICADO en runtime.  
3. eadmin2 `main` no es first-class Linux.  
4. Deps de voz sin pin (RealtimeSTT / torch).  
5. Wayland/COSMIC captura de pantalla: trabajo nuevo, no un fork de OMP.  
6. YouTube IDs del globo se mueren; TOS; OpenSky anónimo en SENTINEL está obsoleto (apagar capa AIR).  
7. Dos WebGL (HUD + iframe) + MediaPipe + 9 HLS = el cuello es decode de video. Unmount **debe** destruir el iframe.  
8. jarvis-hud / Midas sin licencia: tentación de “copiar y listo” = riesgo legal.  
9. Token HA a 10 años = control total de la casa si se filtra.  
10. Prompt injection desde OCR/pantalla: el cerebro debe tratar ese texto como untrusted.

---

## 10. QA por agente + coordinador

Ningún agente implementó código. Cada uno clonó/leyó y corrigió supuestos *antes* de entregar.

### Agente 1 — Cerebro

- Leyó `jarvisbackend`, `server.py`, `HermesAPI`, HUD de eadmin2, docs Hermes, LICENSE de ambos.  
- Corrigió: eadmin2 **no** es el LLM (es el pipeline); `hermes.instructions` **no** se envía en `main`; novik133 **no** es BYOK; memoria de novik133 no persiste; issue #4 ≠ código de `main`; `requirements-client.txt` citado **no existe**.  
- Contrato A2–A5 cubierto con schemas; lo que no existe en los repos está marcado como nuevo.

### Agente 2 — HUD

- Confirmó: no hay `package.json`; MediaPipe **sin pin**; gestos reales = pinch + spread; métricas fake; **sin LICENSE**.  
- Confirmó los nombres `hud.*` del contrato. `hud.click` / `hud.ready` = a construir.  
- Slot `HudViewModule` para el globo; el icosaedro MCU **no** es el host.

### Agente 3 — Globo

- Confirmó Three r128 (no Cesium) y globo 3D real. WebcamMap = Leaflet + JSON.  
- Conflicto real = **dos WebGLRenderer**, no Cesium vs Three. Estrategia: iframe.  
- `map.*` no existe hoy; se traduce a funciones internas. `feeds.json` son placeholders. OpenSky anónimo no es fiable en 2026.

### Agente 4 — Visión

- OMP = Windows + hints, no screen-context. Midas = sin licencia + embeddings cloud.  
- Linux **NO VERIFICADO** en hardware Pop!_OS. Portal = trabajo nuevo.  
- `regions` no lo produce nadie. Computer-use no existe. Cámara excluida.

### Agente 5 — HA

- REST/WS/auth citados a docs oficiales. `POST /api/states` prohibido como control.  
- 100% local solo si HA y dispositivos están en LAN.  
- No clonar core. Cliente nuevo Apache-compatible.

### Coordinador — QA cruzado

Verifiqué yo (no solo los informes):

- `novik133-jarvis/package/metadata.json`: `License: GPL-3.0`, `X-Plasma-API-Minimum-Version: 6.0`.  
- `eadmin2-jarvis_ai/LICENSE`: MIT, Chris Lassiter 2026.  
- `jarvis-hud`: 4 archivos, pinch `d<0.05`, `THREE.WebGLRenderer`, **sin LICENSE**.  
- `sentinel-feed-grid`: Three r128 CDN, `focusLatLon` en `index.html` L814, `LICENSE` MIT, `package.json` `"license": "MIT"`.  
- `WebcamMap/LICENSE.txt` MIT.  
- `openmagicpointer/LICENSE` MIT. `ProjectMidas/LICENSE` **MISSING**.  
- Stats GitHub propias coinciden con los agentes (salvo WebcamMap `open_issues`: API = **6**, agente 3 reportó 3 — GitHub mezcla PRs; dejo 6).  
- Unifiqué envelope, `hud.display.kind`, `hud.set_mode`, vista `map` (no `globe`), gestos, `vision.source`, id de persona `companion`.  
- El workspace `JARVIS-AI` hoy solo tiene README stub + LICENSE Apache-2.0. Cero handlers `map.*` / `hud.*` que romper.

**Incompatibilidades residuales (conscientes, no bugs):**

- eadmin2 hoy habla `summon_panel` / `agent_status` / PCM. El cerebro **traduce** a `hud.*` — capa adapter, no se pide que eadmin2 ya cumpla el envelope.  
- SENTINEL no exporta focus/query hasta el bridge.  
- Visión no corre en Pop!_OS hasta el portal.  
- `instructions` de Hermes: NO VERIFICADO.

---

## 11. Qué se te pide aprobar

1. Cerebro = eadmin2 + Hermes; novik133 = ideas only.  
2. HUD reimplementado; jarvis-hud no se copia.  
3. Globo = vista `map` (iframe SENTINEL) + dataset WebcamMap.  
4. Visión = diseño OMP + portal nativo; Midas = idea OCR.  
5. HA = cliente LAN, core fuera.  
6. Monorepo y envelope de §3–§4.  
7. Persona automática `jarvis` / `companion` sin switch manual.  
8. **No escribir código de producto** hasta que digas que sí.

Cuando apruebes (o ajustes un punto), se implementa Fase 1.
