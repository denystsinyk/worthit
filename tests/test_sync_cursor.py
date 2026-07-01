from unittest.mock import patch

import pytest

from worthit import db, models, sync
from worthit.plaid_client import ItemLoginRequiredError, SyncResult


@pytest.fixture
def conn(tmp_path):
    c = db.get_conn(tmp_path / "test.db")
    db.init_db(c)
    models.upsert_sync_state(c, "item1", "access-token-1", "Amex")
    return c


def _txn(transaction_id, date_str, amount, name=None, merchant_name=None):
    return {
        "transaction_id": transaction_id,
        "account_id": "acc1",
        "date": date_str,
        "amount": amount,
        "merchant_name": merchant_name,
        "name": name,
        "pending": False,
    }


def test_run_sync_persists_transactions_and_advances_cursor(conn):
    result = SyncResult(
        added=[_txn("t1", "2026-06-10", -7.00, name="Amex Dunkin Credit")],
        modified=[],
        removed=[],
        next_cursor="cursor-1",
    )
    with patch("worthit.plaid_client.sync_transactions", return_value=result):
        summaries = sync.run_sync(conn)

    assert len(summaries) == 1
    assert summaries[0].added == 1
    assert not summaries[0].reconnect_required

    state = models.get_sync_state(conn)
    assert state["cursor"] == "cursor-1"
    assert state["last_error"] is None

    txns = models.get_all_transactions(conn)
    assert len(txns) == 1
    assert txns[0]["matched_benefit_id"] == "dunkin"


def test_run_sync_handles_removed_transactions(conn):
    first = SyncResult(
        added=[_txn("t1", "2026-06-10", -7.00, name="Amex Dunkin Credit")],
        modified=[],
        removed=[],
        next_cursor="cursor-1",
    )
    with patch("worthit.plaid_client.sync_transactions", return_value=first):
        sync.run_sync(conn)
    assert len(models.get_all_transactions(conn)) == 1

    second = SyncResult(added=[], modified=[], removed=["t1"], next_cursor="cursor-2")
    with patch("worthit.plaid_client.sync_transactions", return_value=second):
        sync.run_sync(conn)
    assert len(models.get_all_transactions(conn)) == 0


def test_run_sync_records_item_login_required(conn):
    with patch("worthit.plaid_client.sync_transactions", side_effect=ItemLoginRequiredError()):
        summaries = sync.run_sync(conn)

    assert summaries[0].reconnect_required
    state = models.get_sync_state(conn)
    assert state["last_error"] == "ITEM_LOGIN_REQUIRED"


def test_run_sync_does_not_overwrite_manually_labeled_transaction(conn):
    result = SyncResult(
        added=[_txn("t1", "2026-06-10", -7.00, name="Amex Dunkin Credit")],
        modified=[],
        removed=[],
        next_cursor="cursor-1",
    )
    with patch("worthit.plaid_client.sync_transactions", return_value=result):
        sync.run_sync(conn)

    models.label_transaction(conn, "t1", "resy", "actually a resy credit")

    result2 = SyncResult(added=[], modified=[], removed=[], next_cursor="cursor-2")
    with patch("worthit.plaid_client.sync_transactions", return_value=result2):
        sync.run_sync(conn)

    txns = {t["transaction_id"]: t for t in models.get_all_transactions(conn)}
    assert txns["t1"]["matched_benefit_id"] == "resy"
