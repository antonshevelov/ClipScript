# Швидкий старт українською

ClipScript генерує вертикальні відео з JSON-сценаріїв: чат, титульні слайди, запис екрана, outro і озвучка.

## Встановлення

```bash
cd /path/to/clipscript
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Генерація прикладу

```bash
clipscript generate --input examples/scripts/offline-smoke.json --overwrite
```

Результат:

```text
examples/output/offline-smoke.mp4
```

## ElevenLabs

Для якіснішої озвучки:

```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."
```

У шаблоні:

```json
{
  "ttsProvider": "elevenlabs",
  "voice_id": "your_voice_id",
  "elevenlabsModelId": "eleven_multilingual_v2"
}
```

Для брендів краще писати фонетичний варіант у `voiceover`, наприклад `Байно`, а візуально залишати `Baino`.
