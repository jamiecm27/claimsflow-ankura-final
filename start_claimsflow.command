#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -f backend/.env ]; then
  osascript -e 'display alert "ClaimsFlow setup needed" message "Copy your existing backend/.env Gemini key into this version before starting."'
  exit 1
fi
if [ ! -x backend/.venv/bin/python ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/python -m pip install -r backend/requirements.txt
fi
if [ ! -d node_modules ]; then npm install; fi
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 || lsof -nP -iTCP:5174 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 or 5174 is already in use. Stop the old ClaimsFlow servers and try again."
  read -r -p "Press Return to close..." _
  exit 1
fi
cleanup(){ kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true; wait "$BACK_PID" "$FRONT_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
(cd backend && exec .venv/bin/python -m uvicorn app:app --port 8000) & BACK_PID=$!
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort & FRONT_PID=$!
sleep 3
open http://localhost:5174/
echo "ClaimsFlow running. Keep this window open; Control+C stops both servers."
wait "$FRONT_PID"
