"""Mock transaction data for DEMO_MODE. Dates are relative to "today" so the
demo always looks current, no matter when it's viewed. Deliberately covers
one of each dashboard state (complete/partial/pending), so a visitor clicking
through sees the full range of behavior without ever touching a real bank
account or Plaid credential.
"""
from datetime import date, timedelta


def _txn(transaction_id, date_str, amount, merchant_name, name):
    return {
        "transaction_id": transaction_id,
        "item_id": "demo",
        "account_id": "demo",
        "date": date_str,
        "amount": amount,
        "merchant_name": merchant_name,
        "name": name,
        "pending": False,
        "raw_json": None,
    }


def build_demo_transactions(today: date) -> list[dict]:
    month_start = today.replace(day=1)
    # Keep every monthly example on or before today, including on the first
    # few days of a month. Multiple examples sharing a date is realistic and
    # preferable to manufacturing future transactions.
    monthly_dates = [month_start, month_start, min(month_start + timedelta(days=1), today)]
    return [
        # Uber: two orders totaling $14 this month -> spend_threshold complete
        _txn("demo-uber-1", str(monthly_dates[0]), 8.50, "Uber Eats", "UBER *EATS"),
        _txn("demo-uber-2", str(monthly_dates[1]), 5.50, "Uber", "UBER *TRIP"),
        # Dunkin: full credit already posted -> complete
        _txn("demo-dunkin-1", str(monthly_dates[2]), -7.00, None, "AMEX DUNKIN' CREDIT"),
        # Dining: partial credit posted ($6 of $10 cap) -> partial
        _txn("demo-dining-1", str(monthly_dates[2]), -6.00, None, "AMEX Dining Credit"),
        # Resy: purchase happened recently, credit hasn't posted -> "pending" (posting-lag) state
        _txn("demo-resy-purchase-1", str(today - timedelta(days=10)), 45.00, "Resy", "RESY *RESTAURANT BOOKING"),
    ]
