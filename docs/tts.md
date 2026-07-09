# TTS Providers

TTS is only called for a scene with a `voiceover` field. Generated files use an atomic SHA-256 cache key that includes text, provider, voice, voice ID, model, output format, and voice settings.

ClipScript currently supports two text-to-speech providers.

## Edge TTS

Default provider:

```json
{
  "ttsProvider": "edge",
  "voice": "uk-UA-PolinaNeural"
}
```

Pros:

- free;
- no API key;
- useful for drafts and quick iteration.

Cons:

- less natural than premium TTS providers.

## ElevenLabs

```json
{
  "ttsProvider": "elevenlabs",
  "voice_id": "your_voice_id",
  "elevenlabsModelId": "eleven_multilingual_v2"
}
```

Environment variables:

```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."
```

`ELEVENLABS_VOICE_ID` is optional when `voice_id` is present in the template.

## Cache

TTS files are cached under:

```text
.clipscript/cache/tts
```

Override with:

```bash
export CLIPSCRIPT_CACHE_DIR="/absolute/path/to/cache/tts"
```

The cache key includes every sound-affecting provider parameter. Cache replacement is atomic, so failed synthesis cannot leave a partially written entry.

## Pronunciation

For brand names, write phonetic text in `voiceover` while keeping the visual brand name in captions or video. For example:

```json
"voiceover": "Байно. Купуй файно разом."
```
