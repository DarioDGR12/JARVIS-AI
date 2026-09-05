# Probar JARVIS en Pop!_OS

Versión de prueba (ronda 5). Cerebro en `127.0.0.1`. Sin YOLO en el repo. Sin ElevenLabs.

## Instalar

`main` aún no tiene el instalador. Clona la rama del PR:

```bash
git clone -b cursor/integration-plan-5cec https://github.com/DarioDGR12/JARVIS-AI.git
cd JARVIS-AI
bash scripts/popos-trial.sh --apt --hermes
# o, si ya tienes deps: bash scripts/install.sh
```

Si ya clonaste `main`, o el primer `--apt` rompió `dpkg` por el snap de Chromium:

```bash
cd ~/JARVIS-AI
git fetch origin
git checkout cursor/integration-plan-5cec
git pull
sudo dpkg --configure -a
sudo apt-get -f install -y
bash scripts/popos-trial.sh --apt --hermes
```

`--apt` instala Tesseract, ffmpeg, xdotool, webkit (sudo). **No** instala `chromium-browser` (en Pop 24.04 es un snap y suele fallar). El kiosk usa Chrome, Brave o Firefox si ya los tienes.  
`--hermes` clona Hermes Agent en `~/.local/share/jarvis/hermes-agent` (instala `uv` si falta).  
`--stt` instala openWakeWord + faster-whisper en el **venv** (opcional; el HUD ya oye con Web Speech).

El cerebro se instala en `~/.local/share/jarvis/venv` (PEP 668: no se toca el Python del sistema). El comando queda en `~/.local/bin/jarvis`.

```bash
export PATH="$HOME/.local/bin:$PATH"
jarvis doctor
jarvis setup --demo          # o --provider openai --api-key "$OPENAI_API_KEY"
jarvis start                 # Tauri si está compilado; si no, Chromium kiosk
```

La key BYOK va a `~/.hermes/.env` (0600), no al git.

## Qué probar

| Frase / UI | Debe pasar |
|---|---|
| Chat «hola» | Respuesta demo o tu modelo |
| Mic | Web Speech, o PCM si instalaste `[stt]` |
| Visor / Overlay | Ventana compacta / anillo (solo Tauri nativo) |
| «pellizca» / «abre las manos» | Zoom del globo |
| Mapa → pin ISS / JWST | HLS vía proxy (VOD NASA+) |
| Casa | Esquema + habitaciones (token HA opcional) |
| «explica la pantalla» | OCR (Tesseract) |
| «clica en …» / «escribe … en …» | Howdy; record-only salvo `JARVIS_VISION_CLICK=1` |

## Opcional en el portátil

- Howdy enrolado + webcam. `JARVIS_PRESENCE_HOWDY=1` solo calienta `compare.py`.
- `~/.config/jarvis/ha.env` (`HA_URL`, `HA_TOKEN`). Writes piden cara.
- Detector: copia `brain/scripts/detect_template.py` a `~/.local/share/jarvis/detect.py` y `export JARVIS_YOLO_DETECT=…`. YOLO fuera del árbol.
- Voces Chatterbox: WAV de ≥5 s en `~/.local/share/jarvis/voices/`. Los de `voices/` son silencio.
- Tauri nativo: Rust + Node, `cd desktop && npm install && npx tauri build`.

## Unidades

```bash
systemctl --user enable --now jarvis-brain.service
# puerta solo si JARVIS_YOLO_DETECT está en ~/.config/jarvis/door.env
```

Env: `~/.config/jarvis/brain.env` (plantilla en `deploy/env/brain.env.example`).

## No listo

`jarvis doctor` marca `[!!]` lo obligatorio (Python 3.11+, Hermes, HUD Tauri o Chromium, setup, bind 127.0.0.1). Lo demás es `[--]`.
