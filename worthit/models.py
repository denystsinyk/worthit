import json
import sqlite3
from datetime import date, datetime


def get_sync_state(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Returns the single tracked Item's sync state, or None if nothing has been linked yet."""
    row = conn.execute("SELECT * FROM sync_state ORDER BY item_id LIMIT 1").fetchone()
    return row


def get_all_sync_states(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM sync_state").fetchall()


def upsert_sync_state(
    conn: sqlite3.Connection,
    item_id: str,
    access_token: str,
    institution_name: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO sync_state (item_id, access_token, institution_name)
        VALUES (?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            access_token = excluded.access_token,
            institution_name = COALESCE(excluded.institution_name, sync_state.institution_name)
        """,
        (item_id, access_token, institution_name),
    )
    conn.commit()


def update_sync_progress(
    conn: sqlite3.Connection, item_id: str, cursor: str | None, last_error: str | None
) -> None:
    conn.execute(
        """
        UPDATE sync_state
        SET cursor = ?, last_error = ?, last_synced_at = ?
        WHERE item_id = ?
        """,
        (cursor, last_error, datetime.now().isoformat(), item_id),
    )
    conn.commit()


def update_sync_error(conn: sqlite3.Connection, item_id: str, last_error: str) -> None:
    """Record a failed attempt without claiming that a successful sync occurred."""
    conn.execute(
        "UPDATE sync_state SET last_error = ? WHERE item_id = ?",
        (last_error, item_id),
    )
    conn.commit()


def upsert_transactions(conn: sqlite3.Connection, item_id: str, txns: list[dict]) -> None:
    for t in txns:
        conn.execute(
            """
            INSERT INTO transactions
                (transaction_id, item_id, account_id, date, amount, merchant_name, name, pending, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET
                account_id = excluded.account_id,
                date = excluded.date,
                amount = excluded.amount,
                merchant_name = excluded.merchant_name,
                name = excluded.name,
                pending = excluded.pending,
                raw_json = excluded.raw_json
            """,
            (
                t["transaction_id"],
                item_id,
                t.get("account_id"),
                t["date"],
                t["amount"],
                t.get("merchant_name"),
                t.get("name"),
                1 if t.get("pending") else 0,
                # Plaid SDK model dictionaries can contain date/datetime
                # objects; retain their string form in the diagnostic payload.
                json.dumps(t.get("raw_json", t), default=str),
            ),
        )
    conn.commit()


def remove_transactions(conn: sqlite3.Connection, transaction_ids: list[str]) -> None:
    conn.executemany(
        "DELETE FROM transactions WHERE transaction_id = ?",
        [(tid,) for tid in transaction_ids],
    )
    conn.commit()


def get_transactions(
    conn: sqlite3.Connection, start: date, end: date
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM transactions WHERE date >= ? AND date <= ? ORDER BY date",
        (start.isoformat(), end.isoformat()),
    ).fetchall()


def get_all_transactions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM transactions ORDER BY date").fetchall()


def clear_item(conn: sqlite3.Connection, item_id: str) -> None:
    """Remove one Plaid Item and its cached transactions atomically."""
    with conn:
        conn.execute("DELETE FROM transactions WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM sync_state WHERE item_id = ?", (item_id,))
