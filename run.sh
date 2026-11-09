#!/usr/bin/env bash
# Spuštění: ./run.sh  (aplikace poběží na http://127.0.0.1:8000)
set -e
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
