from datetime import date

from worthit.benefits import status
from tests.conftest import make_txn

SETTINGS = {"at_risk_days_monthly": 7, "at_risk_days_semiannual": 21}


def test_complete_state(benefit_by_id):
    dunkin = benefit_by_id["dunkin"]
    txn = make_txn(name="Amex Dunkin Credit", amount=-7.00, date_str="2026-06-10")
    result = status.compute_status(dunkin, [txn], date(2026, 6, 15), SETTINGS)
    assert result.state == "complete"
    assert result.amount_used == 7.00


def test_partial_state(benefit_by_id):
    dining = benefit_by_id["dining"]
    txn = make_txn(merchant_name="Grubhub", name="Amex Dining Credit", amount=-4.00, date_str="2026-06-10")
    result = status.compute_status(dining, [txn], date(2026, 6, 15), SETTINGS)
    assert result.state == "partial"
    assert result.amount_used == 4.00


def test_none_state_when_plenty_of_time_left(benefit_by_id):
    dunkin = benefit_by_id["dunkin"]
    result = status.compute_status(dunkin, [], date(2026, 6, 15), SETTINGS)  # 15 days left, threshold 7
    assert result.state == "none"


def test_at_risk_state_near_period_end(benefit_by_id):
    dunkin = benefit_by_id["dunkin"]
    result = status.compute_status(dunkin, [], date(2026, 6, 25), SETTINGS)  # 5 days left, threshold 7
    assert result.state == "at_risk"


def test_resy_pending_suppresses_at_risk_when_purchase_recent(benefit_by_id):
    resy = benefit_by_id["resy"]
    # 15 days left in the Jan-Jun half (today=6/15, period end=6/30) <= 21-day
    # threshold, which would normally be "at_risk" -- but a qualifying Resy
    # purchase happened recently, so it should show "pending" instead.
    purchase = make_txn(
        transaction_id="purchase1",
        merchant_name="Resy",
        name="Resy Restaurant Booking",
        amount=45.00,
        date_str="2026-06-10",
    )
    result = status.compute_status(resy, [purchase], date(2026, 6, 15), SETTINGS)
    assert result.state == "pending"
    assert result.posting_lag_note is not None


def test_resy_at_risk_without_recent_purchase(benefit_by_id):
    resy = benefit_by_id["resy"]
    result = status.compute_status(resy, [], date(2026, 6, 25), SETTINGS)  # 5 days left
    assert result.state == "at_risk"
    assert result.posting_lag_note is None


def test_semiannual_period_boundaries_on_status(benefit_by_id):
    resy = benefit_by_id["resy"]
    result = status.compute_status(resy, [], date(2026, 3, 1), SETTINGS)
    assert result.period_start == date(2026, 1, 1)
    assert result.period_end == date(2026, 6, 30)
