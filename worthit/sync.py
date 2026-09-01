import sqlite3
from dataclasses import dataclass

from worthit import models, plaid_client


@dataclass
class SyncSummary:
    item_id: str | None
    added: int = 0
    modified: int = 0
    removed: int = 0
    reconnect_required: bool = False
    error: str | None = None


def _normalize(txn: dict) -> dict:
    return {
        "transaction_id": txn["transaction_id"],
        "account_id": txn.get("account_id"),
        "date": str(txn["date"]),
        "amount": float(txn["amount"]),
        "merchant_name": txn.get("merchant_name"),
        "name": txn.get("name"),
        "pending": txn.get("pending", False),
        "raw_json": txn,
    }


def run_sync(conn: sqlite3.Connection) -> list[SyncSummary]:
    """Syncs every linked Item's transactions. Benefit matching happens live at
    read-time (worthit.benefits.status), so this just needs to keep the local
    transaction cache current. Returns one summary per Item so the dashboard
    can report per-connection status."""
    summaries = []
    for state in models.get_all_sync_states(conn):
        item_id = state["item_id"]
        try:
            result = plaid_client.sync_transactions(state["access_token"], state["cursor"])
        except plaid_client.ItemLoginRequiredError:
            models.update_sync_error(conn, item_id, "ITEM_LOGIN_REQUIRED")
            summaries.append(SyncSummary(item_id=item_id, reconnect_required=True, error="ITEM_LOGIN_REQUIRED"))
            continue
        except plaid_client.PlaidSyncError as exc:
            models.update_sync_error(conn, item_id, exc.code)
            summaries.append(SyncSummary(item_id=item_id, error=exc.code))
            continue

        normalized = [_normalize(t) for t in (result.added + result.modified)]
        models.upsert_transactions(conn, item_id, normalized)
        models.remove_transactions(conn, result.removed)
        models.update_sync_progress(conn, item_id, result.next_cursor, None)

        summaries.append(
            SyncSummary(
                item_id=item_id,
                added=len(result.added),
                modified=len(result.modified),
                removed=len(result.removed),
            )
        )

    return summaries
