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
# Швидкий старт

```bash
pip install clipscript==0.2.0
clipscript init my-video
clipscript validate --input my-video/script.json
clipscript preview --input my-video/script.json
clipscript generate --input my-video/script.json
```

`init` створює офлайн-проєкт Schema v2. Для діагностики локального Python, FFmpeg і кешу використовуйте `clipscript doctor`. Неверсіоновані v0.1.0 та Schema v1 сценарії завантажуються сумісно без ручної міграції.

`preview` пише SRT поруч із preview MP4. Навіть якщо production-сценарій має `subtitles.output`, preview не перезаписує цей файл.
