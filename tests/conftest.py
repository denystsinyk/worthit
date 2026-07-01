from datetime import date

import pytest

from worthit.benefits.loader import load_benefits
from worthit.config import BENEFITS_PATH


@pytest.fixture
def benefits():
    return load_benefits(BENEFITS_PATH)


@pytest.fixture
def benefit_by_id(benefits):
    return {b.id: b for b in benefits}


@pytest.fixture
def fixed_today():
    return date(2026, 6, 15)


def make_txn(
    transaction_id="txn1",
    date_str="2026-06-10",
    amount=0.0,
    merchant_name=None,
    name=None,
    matched_benefit_id=None,
    triage_status="unreviewed",
    account_id="acc1",
    item_id="item1",
    pending=0,
):
    """Builds a plain dict standing in for a sqlite3.Row - the code only ever
    accesses rows via row["field"], which dicts support identically."""
    return {
        "transaction_id": transaction_id,
        "item_id": item_id,
        "account_id": account_id,
        "date": date_str,
        "amount": amount,
        "merchant_name": merchant_name,
        "name": name,
        "pending": pending,
        "raw_json": None,
        "matched_benefit_id": matched_benefit_id,
        "triage_status": triage_status,
    }
