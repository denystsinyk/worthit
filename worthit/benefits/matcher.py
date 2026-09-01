import sqlite3
from datetime import date

from worthit.benefits.schema import BenefitConfig, MatchRule


def _combined_text(merchant_name: str | None, name: str | None) -> str:
    return f"{merchant_name or ''} {name or ''}".upper()


def rule_matches(rule: MatchRule, merchant_name: str | None, name: str | None) -> bool:
    """A rule matches if its own substrings all appear (AND), or any of its
    merchant_credit_pairs alternatives match (OR). Substrings from
    merchant_contains and description_contains are both checked against the
    combined merchant_name + name text, since real-world data doesn't
    reliably separate the two fields the same way across transaction types.
    """
    text = _combined_text(merchant_name, name)
    substrings = rule.merchant_contains + rule.description_contains
    direct_match = bool(substrings) and all(s.upper() in text for s in substrings)
    pair_match = any(rule_matches(pair, merchant_name, name) for pair in rule.merchant_credit_pairs)
    return direct_match or pair_match


def _row_in_period(row: sqlite3.Row, start: date, end: date) -> bool:
    row_date = date.fromisoformat(row["date"])
    return start <= row_date <= end


def match_transactions(
    benefit: BenefitConfig, transactions: list[sqlite3.Row], start: date, end: date
) -> list[sqlite3.Row]:
    """Returns transactions in [start, end] that match this benefit's rule and
    have the amount sign appropriate for its detection mode (Plaid convention:
    positive amount = debit/spend, negative = credit/refund)."""
    matched = []
    for row in transactions:
        if not _row_in_period(row, start, end):
            continue
        if benefit.detection_mode == "spend_threshold" and row["amount"] <= 0:
            continue
        if benefit.detection_mode == "credit_match" and row["amount"] >= 0:
            continue
        if rule_matches(benefit.match, row["merchant_name"], row["name"]):
            matched.append(row)
    return matched


def match_purchases_for_lag(
    benefit: BenefitConfig, transactions: list[sqlite3.Row], since: date, until: date
) -> list[sqlite3.Row]:
    """Finds qualifying purchase (debit) transactions for a benefit's posting-lag
    check, using purchase_hint if set, otherwise falling back to the credit match
    rule (useful when the purchase and credit share recognizable merchant text)."""
    hint = benefit.purchase_hint or benefit.match
    matched = []
    for row in transactions:
        row_date = date.fromisoformat(row["date"])
        if not (since <= row_date <= until):
            continue
        if row["amount"] <= 0:
            continue
        if rule_matches(hint, row["merchant_name"], row["name"]):
            matched.append(row)
    return matched


def compute_used_amount(benefit: BenefitConfig, matched_rows: list[sqlite3.Row]) -> float:
    if benefit.detection_mode == "spend_threshold":
        total = sum(row["amount"] for row in matched_rows)
    else:
        total = sum(abs(row["amount"]) for row in matched_rows)
    cap = benefit.amount_cap if benefit.amount_cap is not None else benefit.amount
    return min(total, cap)
