#!/usr/bin/env python3
"""Headless sync entrypoint for cron. Keeps the local transaction cache warm
so the dashboard never needs to make a blocking Plaid call on page load.
Exits non-zero if any linked Item needs
reconnecting, so cron failure notifications (if configured) will fire.

Example crontab entry (every 30 minutes):
  */30 * * * * cd /home/denys/worthit && .venv/bin/python scripts/cron_sync.py >> data/cron_sync.log 2>&1
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worthit import db, sync


def main() -> int:
    conn = db.get_conn()
    db.init_db(conn)
    summaries = sync.run_sync(conn)
    conn.close()

    timestamp = datetime.now().isoformat()
    if not summaries:
        print(f"[{timestamp}] No linked accounts to sync yet - visit /link first.")
        return 0

    exit_code = 0
    for s in summaries:
        if s.reconnect_required:
            print(f"[{timestamp}] Item {s.item_id}: RECONNECT NEEDED ({s.error})")
            exit_code = 1
        else:
            print(
                f"[{timestamp}] Item {s.item_id}: synced "
                f"(added={s.added}, modified={s.modified}, removed={s.removed})"
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
