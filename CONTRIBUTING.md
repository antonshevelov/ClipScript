# Contributing

Thanks for considering a contribution to ClipScript.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before Opening a PR

Run:

```bash
ruff check .
pytest
clipscript generate --input examples/scripts/chat-only.json --overwrite
```

Do not commit generated videos, local caches, API keys, or `.env` files.

## Pull Requests

Good PRs should include:

- a concise problem statement;
- focused code changes;
- docs updates when behavior or configuration changes;
- tests or manual verification notes.

## Code Style

- Keep scene behavior deterministic.
- Prefer explicit JSON schema fields over hidden magic.
- Keep provider-specific logic behind small functions.
- Never log access tokens or secrets.
