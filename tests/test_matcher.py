from datetime import date

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


def test_confirmed_dunkin_real_pattern(benefit_by_id):
    dunkin = benefit_by_id["dunkin"]
    txn = make_txn(name="Amex Dunkin Credit", amount=-7.00, date_str="2026-06-10")
    matched = matcher.match_transactions(dunkin, [txn], date(2026, 6, 1), date(2026, 6, 30))
    assert len(matched) == 1
    assert matcher.compute_used_amount(dunkin, matched) == 7.00


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


def test_rematch_all_skips_labeled_and_ignored(benefits, tmp_path):
    from worthit import db, models

    conn = db.get_conn(tmp_path / "test.db")
    db.init_db(conn)

    models.upsert_transactions(
        conn,
        "item1",
        [
            {"transaction_id": "t1", "date": "2026-06-10", "amount": -7.00, "merchant_name": None, "name": "Amex Dunkin Credit"},
            {"transaction_id": "t2", "date": "2026-06-11", "amount": -7.00, "merchant_name": None, "name": "Amex Dunkin Credit"},
        ],
    )
    # Manually label t2 as belonging to "resy" (simulating a user override);
    # rematch_all must not clobber that even though it would otherwise match dunkin.
    models.label_transaction(conn, "t2", "resy", "user says this is actually resy")

    matcher.rematch_all(conn, benefits)

    rows = {r["transaction_id"]: r for r in models.get_all_transactions(conn)}
    assert rows["t1"]["matched_benefit_id"] == "dunkin"
    assert rows["t2"]["matched_benefit_id"] == "resy"
