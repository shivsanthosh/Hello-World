#!/usr/bin/env bash
# Build the UI and serve the whole application on http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r backend/requirements.txt
(cd frontend && npm install --silent && npm run build --silent)
cd backend && exec uvicorn app.main:app --port "${PORT:-8000}"
