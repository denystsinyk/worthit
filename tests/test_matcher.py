from datetime import date

import pytest

from worthit.benefits import matcher
from worthit.benefits.schema import MatchRule
from tests.conftest import make_txn


def test_rule_matches_case_insensitive_and_semantics():
    rule = MatchRule(description_contains=["DUNKIN", "CREDIT"])
    assert matcher.rule_matches(rule, None, "Amex dunkin credit")
    assert not matcher.rule_matches(rule, None, "Amex dunkin purchase")


def test_rule_matches_merchant_field():
    rule = MatchRule(merchant_contains=["UBER"])
    assert matcher.rule_matches(rule, "Uber Eats", None)
    assert not matcher.rule_matches(rule, "Lyft", None)


def test_rule_matches_or_via_pairs():
    rule = MatchRule(
        merchant_credit_pairs=[
            MatchRule(merchant_contains=["GRUBHUB"], description_contains=["CREDIT"]),
            MatchRule(merchant_contains=["FIVE GUYS"], description_contains=["CREDIT"]),
        ]
    )
    assert matcher.rule_matches(rule, "Grubhub", "Amex Dining Credit")
    assert matcher.rule_matches(rule, "Five Guys", "Amex Dining Credit")
    assert not matcher.rule_matches(rule, "Chipotle", "Amex Dining Credit")


@pytest.mark.parametrize(
    ("benefit_id", "description", "amount"),
    [
        ("dining", "AMEX DINING CREDIT", -10.00),
        ("dunkin", "AMEX DUNKIN' CREDIT", -7.00),
        ("resy", "AMEX RESY CREDIT", -50.00),
    ],
)
def test_confirmed_real_statement_credit_patterns(
    benefit_by_id, benefit_id, description, amount
):
    benefit = benefit_by_id[benefit_id]
    txn = make_txn(name=description, amount=amount, date_str="2026-06-10")
    matched = matcher.match_transactions(benefit, [txn], date(2026, 1, 1), date(2026, 6, 30))
    assert len(matched) == 1
    assert matcher.compute_used_amount(benefit, matched) == abs(amount)


def test_statement_credit_benefits_are_marked_as_requiring_enrollment(benefit_by_id):
    assert benefit_by_id["dining"].enrollment_required
    assert benefit_by_id["dunkin"].enrollment_required
    assert benefit_by_id["resy"].enrollment_required


def test_uber_spend_threshold(benefit_by_id):
    uber = benefit_by_id["uber"]
    txns = [
        make_txn(transaction_id="t1", name="Uber Eats", amount=6.00, date_str="2026-06-05"),
        make_txn(transaction_id="t2", name="Uber Trip", amount=6.00, date_str="2026-06-20"),
    ]
    matched = matcher.match_transactions(uber, txns, date(2026, 6, 1), date(2026, 6, 30))
    assert len(matched) == 2
    assert matcher.compute_used_amount(uber, matched) == 10.00  # capped at benefit amount


def test_uber_ignores_credit_transactions(benefit_by_id):
    uber = benefit_by_id["uber"]
    txns = [make_txn(name="Uber Eats", amount=-6.00, date_str="2026-06-05")]
    matched = matcher.match_transactions(uber, txns, date(2026, 6, 1), date(2026, 6, 30))
    assert matched == []


def test_period_filtering_excludes_out_of_range(benefit_by_id):
    dunkin = benefit_by_id["dunkin"]
    txn = make_txn(name="Amex Dunkin Credit", amount=-7.00, date_str="2026-05-31")
    matched = matcher.match_transactions(dunkin, [txn], date(2026, 6, 1), date(2026, 6, 30))
    assert matched == []


def test_credit_match_capped_at_amount_cap(benefit_by_id):
    dining = benefit_by_id["dining"]
    txns = [
        make_txn(transaction_id="t1", merchant_name="Grubhub", name="Amex Dining Credit", amount=-6.00, date_str="2026-06-05"),
        make_txn(transaction_id="t2", merchant_name="Grubhub", name="Amex Dining Credit", amount=-8.00, date_str="2026-06-20"),
    ]
    matched = matcher.match_transactions(dining, txns, date(2026, 6, 1), date(2026, 6, 30))
    assert len(matched) == 2
    assert matcher.compute_used_amount(dining, matched) == 10.00  # 14 raw, capped at 10
