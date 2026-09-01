from datetime import date

from worthit import demo_data
from worthit.benefits import status


def test_demo_data_showcases_each_dashboard_state(benefit_by_id):
    today = date(2026, 6, 15)
    txns = demo_data.build_demo_transactions(today)
    settings = {"at_risk_days_monthly": 7, "at_risk_days_semiannual": 21}

    statuses = {
        b_id: status.compute_status(b, txns, today, settings)
        for b_id, b in benefit_by_id.items()
    }

    assert statuses["uber"].state == "complete"
    assert statuses["dunkin"].state == "complete"
    assert statuses["dining"].state == "partial"
    # Resy: recent qualifying purchase, no credit posted yet -> pending, not at_risk
    assert statuses["resy"].state == "pending"
    assert statuses["resy"].posting_lag_note is not None


def test_demo_data_never_manufactures_future_transactions():
    today = date(2026, 9, 1)
    txns = demo_data.build_demo_transactions(today)

    assert all(date.fromisoformat(txn["date"]) <= today for txn in txns)
