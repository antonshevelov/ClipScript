# Development

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run

```bash
clipscript validate --input examples/scripts/chat-only.json
clipscript generate --input examples/scripts/chat-only.json --overwrite
```

## Checks

```bash
ruff check .
pytest
python -m py_compile src/clipscript/cli.py
```

## Release Checklist

1. Update `CHANGELOG.md`.
2. Run tests and lint.
3. Render `examples/scripts/chat-only.json`.
4. Confirm generated MP4 is `1080x1920`, has audio, and opens in a standard player.
5. Tag the release.

## Design Notes

- Scenario-relative paths make examples portable.
- Template-relative logo paths let teams keep brand assets near templates.
- TTS output is cached to keep iterative rendering fast.
- Generated media is ignored by git.
