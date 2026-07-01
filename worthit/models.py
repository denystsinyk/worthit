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
                json.dumps(t.get("raw_json", t)),
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


def get_transaction(conn: sqlite3.Connection, transaction_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)
    ).fetchone()


def set_matched_benefit(conn: sqlite3.Connection, transaction_id: str, benefit_id: str | None) -> None:
    conn.execute(
        "UPDATE transactions SET matched_benefit_id = ? WHERE transaction_id = ?",
        (benefit_id, transaction_id),
    )
    conn.commit()


def get_unreviewed_credits(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM transactions
        WHERE amount < 0 AND matched_benefit_id IS NULL AND triage_status = 'unreviewed'
        ORDER BY date DESC
        """
    ).fetchall()


def label_transaction(
    conn: sqlite3.Connection,
    transaction_id: str,
    assigned_benefit_id: str | None,
    note: str,
) -> None:
    triage_status = "ignored" if assigned_benefit_id is None else "labeled"
    conn.execute(
        "UPDATE transactions SET matched_benefit_id = ?, triage_status = ? WHERE transaction_id = ?",
        (assigned_benefit_id, triage_status, transaction_id),
    )
    conn.execute(
        """
        INSERT INTO triage_labels (transaction_id, assigned_benefit_id, note, labeled_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(transaction_id) DO UPDATE SET
            assigned_benefit_id = excluded.assigned_benefit_id,
            note = excluded.note,
            labeled_at = excluded.labeled_at
        """,
        (transaction_id, assigned_benefit_id, note, datetime.now().isoformat()),
    )
    conn.commit()
