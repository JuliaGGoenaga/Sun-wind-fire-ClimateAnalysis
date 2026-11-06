#!/usr/bin/env bash
# Crea el entorno la primera vez y arranca la webapp en http://localhost:8000
set -e
cd "$(dirname "$0")"
# (re)create the environment if it is missing or broken (e.g. after moving the folder)
if ! .venv/bin/python -c "import uvicorn, ladybug" >/dev/null 2>&1; then
  rm -rf .venv
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/uvicorn app.main:app --port "${PORT:-8000}" --reload --reload-dir app --reload-dir report --reload-dir layout
