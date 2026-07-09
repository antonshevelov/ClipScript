# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run

```bash
clipscript validate --input examples/scripts/offline-smoke.json
clipscript generate --input examples/scripts/offline-smoke.json --overwrite
```

`chat-only.json` uses Edge TTS and needs network access. `app-demo.json` deliberately references a screen recording that is not included in the repository.

## Checks

```bash
ruff check .
mypy src tests
pytest
python -m build
```

`pytest -m smoke` performs an offline MoviePy render and verifies the generated MP4 dimensions and FPS.

## Release Checklist

1. Update `CHANGELOG.md`.
2. Run lint, typecheck, unit tests, smoke render, and package build.
3. Validate `examples/scripts/offline-smoke.json` and `examples/scripts/chat-only.json`.
4. Confirm the CI matrix for Python 3.9 through 3.12 remains green.

## Design Notes

- `clipscript.models` owns strict Schema v2 and legacy migration occurs in `clipscript.project`.
- `clipscript.renderers` and `clipscript.tts` use registries for new implementations.
- Those registries are internal Python dependency-injection points; ClipScript does not expose a JSON plugin protocol.
- `clipscript.media` is the sole MoviePy 2.x boundary; the engine tracks and closes all MoviePy clips.
- TTS cache entries use atomic writes and SHA-256 keys over every sound-affecting setting.
## Full Release Gate

Run the full local release gate with:

```bash
ruff check .
mypy src tests
pytest
python -m build
python -m pip install --force-reinstall dist/*.whl
clipscript schema --output /tmp/clipscript-schema.json
```

Offline media tests use local MoviePy/FFmpeg only. Do not add live Edge or ElevenLabs calls to tests or CI.
