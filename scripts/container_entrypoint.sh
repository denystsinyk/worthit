#!/bin/sh
set -eu

python scripts/check_config.py
exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 --timeout 120 app:app
