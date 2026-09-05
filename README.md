# JARVIS

App de escritorio (Tauri). Tú pones la key del modelo (**BYOK**). La voz es local. No se entrena nada aquí.

**Probar en Pop!_OS:** [docs/POPOS.md](docs/POPOS.md)

```bash
git clone -b cursor/integration-plan-5cec https://github.com/DarioDGR12/JARVIS-AI.git
cd JARVIS-AI
bash scripts/popos-trial.sh --apt --hermes
export PATH="$HOME/.local/bin:$PATH"
jarvis doctor
jarvis start
```

Sin Tauri compilado, `jarvis start` abre Chromium kiosk. La ventana nativa es el producto.

```bash
jarvis setup --demo
# o: jarvis setup --provider openai --api-key "$OPENAI_API_KEY"
jarvis start --hud kiosk    # forzar kiosk
jarvis serve                # solo API 127.0.0.1:8765
```

Terminal (opcional):

```bash
jarvis chat -m "hola"
jarvis speak -m "Sistemas en línea."
jarvis status
jarvis doctor
```

## BYOK

El cerebro **no** llama a OpenAI/Anthropic. Llama a [Hermes Agent](https://github.com/NousResearch/hermes-agent) en `127.0.0.1:8642`. Hermes usa **tu** key.

| Qué | Dónde | En git |
|---|---|---|
| Key del modelo | `~/.hermes/.env` (permiso 0600) | No |
| Proveedor / modelo | `~/.hermes/config.yaml` | No |
| Modo producto | `~/.config/jarvis/product.yaml` | No |

Sin key: `setup --demo`. Con key: el mismo producto, tu modelo. También **Ajustes** en la app.

## Requisitos

- Pop!_OS (Linux). Python 3.11+.
- Hermes Agent (`hermes gateway`). `bash scripts/install-hermes.sh`
- Piper: lo instala `scripts/install.sh`.
- HUD: Tauri (Rust + Node) o Chromium.

## Qué hay

HUD (inicio, chat, sistema, casa, mapa, visión, ajustes), globo SENTINEL, captura, webcam del HUD (una `getUserMedia`; Howdy `hold` suelta V4L2), gestos pellizca/abre, HA REST + WebSocket, phrase-map, officer, memoria JSONL + mem0 opcional. HLS NASA+ vía proxy. Detector fuera del árbol.

## Qué no entra

YOLO/ultralytics en el repo (`JARVIS_YOLO_DETECT`). `Memory()` default (OpenAI + PostHog). ElevenLabs. MediaPipe CDN.

Licencia Apache-2.0. Agentes: [docs/AGENTS.md](docs/AGENTS.md). Plan: [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md).
