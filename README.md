# ClipScript

ClipScript generates vertical MP4 videos from JSON scripts. It supports timed chat, image, title, video, and outro scenes; transitions, subtitles, audio mixing, and portable assets.

## Status

`0.2.0` adds strict Schema v2, creator workflow commands, and compatibility loading for v0.1.0/v0.1.1 projects.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

clipscript generate --input examples/scripts/offline-smoke.json --overwrite
```

This writes `examples/output/offline-smoke.mp4`. The example is runnable without TTS, network access, or external media files.

## Schema v2

New scripts require `schemaVersion: 2`. Voiceover is optional and belongs to the scene that needs it; a scene without `voiceover` never invokes TTS.

```json
{
  "schemaVersion": 2,
  "title": "Chat problem demo",
  "output": "../output/chat-only.mp4",
  "template": "../templates/default.json",
  "scenes": [
    {
      "type": "chat",
      "duration": 8,
      "voiceover": "A shared list in a chat looks simple at first.",
      "chatHeader": false,
      "senderNames": false,
      "participantCount": 2,
      "messages": [{"text": "What should I buy?", "at": 0.5}, {"text": "Milk, bread, eggs", "side": "right", "typing": 0.4}]
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

The schema is strict: unknown fields, wrong scene field combinations, invalid trim/crop values, invalid FPS, and invalid resolution are rejected. See `docs/script-format.md` for the complete format.

Use `clipscript init PATH` for an offline starter, `clipscript preview --input script.json` for a draft, `clipscript doctor` for local diagnostics, and `clipscript schema` for machine-readable Schema v2.

## Scene Types

- `chat`: timed structured messages, duration, and chat presentation options.
- `image`: local image with required duration and `contain`/`cover` fitting.
- `title` and `outro`: require duration and caption.
- `video`: requires `src` and duration; source audio is muted unless `sourceAudioVolume` is positive.

Paths in scripts are relative to the script file. Template `logo` is relative to the template file.

## TTS

The default Edge provider needs no key. ElevenLabs uses `ELEVENLABS_API_KEY` and template `voice_id` (or `ELEVENLABS_VOICE_ID`). The cache uses atomic writes and SHA-256 keys over every sound-affecting setting. See `docs/tts.md`.

## Examples and Compatibility

- `examples/scripts/offline-smoke.json` is the runnable offline example.
- `examples/scripts/image-scene.json` is a runnable image/SRT example with a committed neutral asset.
- `examples/scripts/chat-only.json` is runnable but uses network Edge TTS.
- `examples/scripts/legacy-v0.json` is a loadable 0.1.0-format compatibility fixture.
- `examples/scripts/app-demo.json` intentionally requires `examples/assets/app-demo.mp4`; add a real screen recording before validating or rendering it.

Unversioned v0.1.0 scripts and Schema v1 scripts normalize automatically into the v2 runtime. Their legacy string chat messages retain automatic alternating sides and their original timing fallback behavior.

The Python module API is alpha and changed in 0.1.1: import models from `clipscript.models`, project loading from `clipscript.project`, and rendering from `clipscript.engine`. Imports from the old monolithic `clipscript.cli` module are not a compatibility surface.

Renderer and TTS registries are internal dependency-injection extension points for Python integrations, not a JSON plugin API.

## Development

```bash
ruff check .
mypy src tests
pytest
python -m build
```

Further guidance: `docs/development.md`, `docs/script-format.md`, and `docs/tts.md`.
