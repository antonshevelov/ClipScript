#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

mkdir -p examples/output examples/assets .clipscript/cache/tts

echo "Setup complete."
echo "Run:"
echo "  source .venv/bin/activate"
echo "  clipscript validate --input examples/scripts/offline-smoke.json"
echo "  clipscript generate --input examples/scripts/offline-smoke.json --overwrite"
