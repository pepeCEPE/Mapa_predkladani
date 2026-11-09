#!/usr/bin/env bash
# Spuštění: ./run.sh  -> http://127.0.0.1:8000
cd "$(dirname "$0")"
exec python3 start.py
