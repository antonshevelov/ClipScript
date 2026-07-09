# ClipScript

ClipScript is a script-driven vertical video generator for social promos, tutorials, product demos, Reels, Shorts, and TikTok-style clips.

It turns JSON scripts into `1080x1920` MP4 videos with:

- animated chat scenes;
- static title and outro scenes;
- real screen recordings embedded as video scenes;
- voiceover generated with Microsoft Edge TTS or ElevenLabs;
- brand templates for colors, fonts, logos, and output settings.

ClipScript is designed for repeatable content production: write the script once, render consistently, iterate quickly.

## Status

Alpha. The core renderer works, but the scene schema and CLI may still change before `1.0`.

## Quick Start

```bash
git clone https://github.com/antonshevelov/ClipScript.git
cd ClipScript

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

clipscript generate --input examples/scripts/chat-only.json --overwrite
```

The generated file will be written to:

```text
examples/output/chat-only.mp4
```

## Script Format

A script is a JSON file with:

- `title` - internal video name;
- `output` - final MP4 path, relative to the script file;
- `template` - style template path, relative to the script file;
- `voiceover` - one voiceover text per scene;
- `scenes` - ordered scene definitions.

Minimal example:

```json
{
  "title": "Chat problem demo",
  "output": "../output/chat-only.mp4",
  "template": "../templates/default.json",
  "voiceover": [
    "A shared list in a chat looks simple at first.",
    "But after a few messages, it is already hard to find.",
    "Use a shared list instead."
  ],
  "scenes": [
    {
      "type": "chat",
      "duration": 8,
      "chatHeader": false,
      "senderNames": false,
      "participantCount": 2,
      "messages": ["What should I buy?", "Milk, bread, eggs", "I am near the store"]
    },
    {
      "type": "title",
      "duration": 1.5,
      "caption": "Sound familiar?"
    },
    {
      "type": "outro",
      "duration": 3,
      "caption": "Make short demos from scripts"
    }
  ]
}
```

## Scene Types

### `chat`

Animated message stream. Useful for showing a problem, conversation, or before-state.

Common fields:

- `messages`: array of message strings;
- `duration`: requested duration in seconds;
- `chatHeader`: show/hide header;
- `chatTitle`: header title;
- `chatSubtitle`: header subtitle;
- `senderNames`: show/hide sender names;
- `participantCount`: `2` or `3`.

### `title`

Centered text slide for transitions and hooks.

### `video`

Embeds a real video recording.

Common fields:

- `src`: path to an MP4/MOV file, relative to the script file;
- `start` / `end`: trim source video;
- `crop`: `[x1, y1, x2, y2]`;
- `backgroundColor`: background behind contained video;
- `caption`: optional burned-in caption.

### `outro`

Brand-colored final screen with optional logo, caption, and optional `url`.

## Template Format

See `examples/templates/default.json`.

```json
{
  "resolution": [1080, 1920],
  "fps": 30,
  "brandColor": "#0f7b6c",
  "surfaceColor": "#fdf9f1",
  "textColor": "#17211f",
  "accentColor": "#43a047",
  "logo": null,
  "voice": "uk-UA-PolinaNeural",
  "voice_id": null,
  "elevenlabsModelId": "eleven_multilingual_v2",
  "fontFamily": "system",
  "ttsProvider": "edge"
}
```

## TTS Providers

### Edge TTS

Default provider. Free and does not require API keys.

```json
{
  "ttsProvider": "edge",
  "voice": "uk-UA-PolinaNeural"
}
```

### ElevenLabs

Higher-quality voiceover through the ElevenLabs API.

```json
{
  "ttsProvider": "elevenlabs",
  "voice_id": "your_voice_id",
  "elevenlabsModelId": "eleven_multilingual_v2"
}
```

Environment:

```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..." # optional if voice_id is set in template
```

Secrets are read from environment variables and are never printed intentionally.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

clipscript validate --input examples/scripts/chat-only.json
ruff check .
pytest
```

## Documentation

- `docs/script-format.md`
- `docs/tts.md`
- `docs/development.md`
- `docs/uk/quickstart.md`

## License

MIT.
