# JARVIS

Asistente personal local. Tú pones la key del modelo (**BYOK**). La voz es local. No se entrena nada aquí.

```bash
# 1. Instalar
bash scripts/install.sh

# 2a. Probar sin key (modelo mock local)
python3 -m jarvis_brain setup --demo

# 2b. O tu key (nunca se sube a git)
python3 -m jarvis_brain setup --provider openai --api-key "$OPENAI_API_KEY"
# también: anthropic | openrouter | custom --base-url http://127.0.0.1:11434/v1

# 3. Arrancar el producto
python3 -m jarvis_brain start
# abre http://127.0.0.1:8765/
```

En la consola escribes; JARVIS responde y habla (Piper). En terminal:

```bash
python3 -m jarvis_brain chat -m "hola"
python3 -m jarvis_brain speak -m "Sistemas en línea."
python3 -m jarvis_brain status
```

## BYOK

El cerebro **no** llama a OpenAI/Anthropic. Llama a [Hermes Agent](https://github.com/NousResearch/hermes-agent) en `127.0.0.1:8642`. Hermes usa **tu** key.

| Qué | Dónde | En git |
|---|---|---|
| Key del modelo | `~/.hermes/.env` (permiso 0600) | No |
| Proveedor / modelo | `~/.hermes/config.yaml` | No |
| Modo producto | `~/.config/jarvis/product.yaml` | No |
| Auth del API local de Hermes | `API_SERVER_KEY` (≥16 chars) | No — no es la key del LLM |

Sin key: `setup --demo` (producto completo, modelo falso). Con key: el mismo producto, tu modelo.

## Requisitos

- Linux (Pop!_OS). Python 3.11+.
- Hermes Agent instalado (`hermes gateway`).
- Piper se descarga con `brain/scripts/setup_piper.sh` (CPU). Chatterbox = GPU, opcional.

## Qué no está (aún)

HUD Iron Man, Howdy, Home Assistant, mem0, globo, visión, vigilancia. El núcleo usable sí: setup, consola, chat, voz.

Plan largo: [docs/INTEGRATION_PLAN.md](docs/INTEGRATION_PLAN.md). Licencia Apache-2.0.
