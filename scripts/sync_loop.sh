#!/bin/sh
set -u

python scripts/check_config.py || exit 1

while true; do
  python scripts/cron_sync.py || true
  sleep "${SYNC_INTERVAL_SECONDS:-1800}"
done
