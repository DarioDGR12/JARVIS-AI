# Voces locales (Chatterbox)

`jarvis.wav` y `companion.wav` de este directorio son **marcadores de ruta** (silencio corto). No son clones.

Chatterbox necesita un WAV de habla real de **al menos 5 segundos**. Pon los tuyos en:

- `~/.local/share/jarvis/voices/jarvis.wav`
- `~/.local/share/jarvis/voices/companion.wav`

o apunta `JARVIS_VOICE_JARVIS` / `JARVIS_VOICE_COMPANION`.

ElevenLabs está prohibido. El cerebro resuelve primero env, luego `~/.local/share/jarvis/voices/`, luego este directorio.
