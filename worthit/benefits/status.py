import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from worthit.benefits import matcher
from worthit.benefits.periods import current_period, days_remaining
from worthit.benefits.schema import BenefitConfig

State = Literal["complete", "partial", "none", "at_risk", "pending"]

DEFAULT_AT_RISK_DAYS_MONTHLY = 7
DEFAULT_AT_RISK_DAYS_SEMIANNUAL = 21


@dataclass
class BenefitStatus:
    benefit: BenefitConfig
    period_start: date
    period_end: date
    amount_used: float
    amount_total: float
    state: State
    days_remaining: int
    posting_lag_note: str | None = None


def compute_status(
    benefit: BenefitConfig,
    all_transactions: list[sqlite3.Row],
    today: date,
    settings: dict | None = None,
) -> BenefitStatus:
    settings = settings or {}
    start, end = current_period(benefit, today)
    matched = matcher.match_transactions(benefit, all_transactions, start, end)
    used = matcher.compute_used_amount(benefit, matched)
    cap = benefit.amount_cap if benefit.amount_cap is not None else benefit.amount
    days_left = days_remaining(end, today)

    at_risk_days = settings.get(
        "at_risk_days_monthly" if benefit.period == "monthly" else "at_risk_days_semiannual",
        DEFAULT_AT_RISK_DAYS_MONTHLY if benefit.period == "monthly" else DEFAULT_AT_RISK_DAYS_SEMIANNUAL,
    )

    posting_lag_note = None
    if used >= cap:
        state: State = "complete"
    elif used > 0:
        state = "partial"
    else:
        state = "at_risk" if days_left <= at_risk_days else "none"

        if benefit.posting_lag_days > 0 and state == "at_risk":
            lag_start = today - timedelta(days=benefit.posting_lag_days)
            pending_purchases = matcher.match_purchases_for_lag(
                benefit, all_transactions, lag_start, today
            )
            if pending_purchases:
                state = "pending"
                posting_lag_note = (
                    f"Found {len(pending_purchases)} qualifying purchase(s) in the last "
                    f"{benefit.posting_lag_days} days — the credit can take that long to post, "
                    "so this isn't flagged as at-risk yet."
                )

    return BenefitStatus(
        benefit=benefit,
        period_start=start,
        period_end=end,
        amount_used=used,
        amount_total=cap,
        state=state,
        days_remaining=days_left,
        posting_lag_note=posting_lag_note,
    )
