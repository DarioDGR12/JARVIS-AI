# JARVIS

App de escritorio (Tauri). Tú pones la key del modelo (**BYOK**). La voz es local. No se entrena nada aquí.

```bash
bash scripts/install.sh
jarvis setup --demo
# o: jarvis setup --provider openai --api-key "$OPENAI_API_KEY"
jarvis start
```

`jarvis start` abre la **ventana nativa**, no el navegador. En la app: chat, voz (Piper), ajustes BYOK, bandeja.

Terminal (opcional):

```bash
jarvis chat -m "hola"
jarvis speak -m "Sistemas en línea."
jarvis status
jarvis serve          # solo API local, sin ventana
```

## BYOK

El cerebro **no** llama a OpenAI/Anthropic. Llama a [Hermes Agent](https://github.com/NousResearch/hermes-agent) en `127.0.0.1:8642`. Hermes usa **tu** key.

| Qué | Dónde | En git |
|---|---|---|
| Key del modelo | `~/.hermes/.env` (permiso 0600) | No |
| Proveedor / modelo | `~/.hermes/config.yaml` | No |
| Modo producto | `~/.config/jarvis/product.yaml` | No |

Sin key: `setup --demo`. Con key: el mismo producto, tu modelo. También se configura desde **Ajustes** en la app.

## Requisitos

- Linux (Pop!_OS). Python 3.11+. Rust (para la app Tauri).
- Hermes Agent (`hermes gateway`).
- Piper: `brain/scripts/setup_piper.sh`.

## Qué no está (aún)

HUD Iron Man, globo, visión de pantalla, vigilancia YOLO, mem0 OSS (Qdrant+Ollama).
Howdy / HA / phrase-map / stats / memoria local JSON **sí están** en el cerebro y en la app.

Licencia Apache-2.0. Plan largo: [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md).
