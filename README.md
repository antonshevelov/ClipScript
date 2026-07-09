# ClipScript

ClipScript generates vertical MP4 videos from JSON scripts. It supports animated chat, title, video, and outro scenes; Edge and ElevenLabs voiceover; portable scenario-relative assets; and template-relative logos.

## Status

`0.1.1` stabilizes the core around strict Schema v1, MoviePy 2.x, extensible renderer/TTS registries, and deterministic media cleanup. It remains an alpha release.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

clipscript generate --input examples/scripts/offline-smoke.json --overwrite
```

This writes `examples/output/offline-smoke.mp4`. The example is runnable without TTS, network access, or external media files.

## Schema v1

New scripts require `schemaVersion: 1`. Voiceover is optional and belongs to the scene that needs it; a scene without `voiceover` never invokes TTS.

```json
{
  "schemaVersion": 1,
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

The schema is strict: unknown fields, wrong scene field combinations, invalid trim/crop values, invalid FPS, and invalid resolution are rejected. See `docs/script-format.md` for the complete format.

Both CLI commands require an explicit `--input` path, so installed packages do not rely on repository examples.

## Scene Types

- `chat`: animated messages, duration, and chat presentation options.
- `title`: Schema v1 requires duration and caption.
- `video`: Schema v1 requires `src` and either `duration` or `end`; the result is clamped to source media length.
- `outro`: Schema v1 requires duration and caption, with optional URL.

Paths in scripts are relative to the script file. Template `logo` is relative to the template file.

## TTS

The default Edge provider needs no key. ElevenLabs uses `ELEVENLABS_API_KEY` and template `voice_id` (or `ELEVENLABS_VOICE_ID`). The cache uses atomic writes and SHA-256 keys over every sound-affecting setting. See `docs/tts.md`.

## Examples and Compatibility

- `examples/scripts/offline-smoke.json` is the runnable offline example.
- `examples/scripts/chat-only.json` is runnable but uses network Edge TTS.
- `examples/scripts/legacy-v0.json` is a loadable 0.1.0-format compatibility fixture.
- `examples/scripts/app-demo.json` intentionally requires `examples/assets/app-demo.mp4`; add a real screen recording before validating or rendering it.

Unversioned 0.1.0 scripts with a root `voiceover` array remain supported. The loader migrates matching entries to scene-level voiceover before validation; scenes without timing use voiceover duration or a 5-second fallback. Versioned Schema v1 scripts must not include root `voiceover`; this is the only format-level breaking change in 0.1.1.

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
