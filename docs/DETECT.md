# Detector fuera del árbol

YOLO / ultralytics es AGPL. **No** entra en este repo.

## Contrato JSONL

El cerebro lanza `$JARVIS_YOLO_DETECT` (o `~/.local/share/jarvis/detect.py`).

stdin (una línea por tick):

```json
{"type":"tick","camera":"door","timestamp":1710000000000}
{"type":"frame","camera":"door","jpeg_b64":"..."}
```

stdout:

```json
{"type":"detection","kind":"person","camera":"door","score":0.8,"text":"visita"}
```

## Instalación

```bash
mkdir -p ~/.local/share/jarvis
cp brain/scripts/detect_template.py ~/.local/share/jarvis/detect.py
# edita detect() y carga YOLO26n ahí
export JARVIS_YOLO_DETECT=~/.local/share/jarvis/detect.py
```

El stub `brain/scripts/detect_stub.py` solo prueba el protocolo. No es un detector.

Unidad systemd de usuario (`deploy/systemd/jarvis-door.service`): solo si
`JARVIS_YOLO_DETECT` apunta a **tu** script fuera del repo. El cerebro también
lanza ese hijo al armar. ultralytics no se instala desde aquí.
