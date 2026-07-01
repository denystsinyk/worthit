import sqlite3

from worthit.config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_state (
    item_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    cursor TEXT,
    last_synced_at TEXT,
    last_error TEXT,
    institution_name TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    account_id TEXT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    merchant_name TEXT,
    name TEXT,
    pending INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT,
    matched_benefit_id TEXT,
    triage_status TEXT NOT NULL DEFAULT 'unreviewed'
);

CREATE TABLE IF NOT EXISTS triage_labels (
    transaction_id TEXT PRIMARY KEY,
    assigned_benefit_id TEXT,
    note TEXT,
    labeled_at TEXT
);
"""


def get_conn(db_path=None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
