#!/usr/bin/env bash
# Start Topic Scout on this Mac. Uses uv to get Python 3.12 and the dependencies automatically.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Create .env first: cp .env.example .env, then fill it in."; exit 1; }
if ! command -v uv >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install uv; else curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; fi
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
# caffeinate -i keeps the Mac from idle-sleeping while the server runs (the lid still sleeps it unless on power with a display)
exec caffeinate -i "$UV" run --python 3.12 --with-requirements requirements.txt server.py
