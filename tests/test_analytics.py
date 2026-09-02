from datetime import date
from decimal import Decimal

from worthit.analytics import build_report

from conftest import make_txn


def test_report_tracks_captured_missed_and_current_value(benefit_by_id):
    uber = benefit_by_id["uber"]
    rows = [
        make_txn("coverage", "2026-01-01", 1, "Other", "OTHER"),
        make_txn("jan", "2026-01-10", 10, "Uber", "UBER"),
        make_txn("mar", "2026-03-04", 5, "Uber", "UBER"),
    ]

    report = build_report([uber], rows, date(2026, 3, 15), {"annual_fee": 325})

    assert report.captured == Decimal("15.00")
    assert report.available == Decimal("30.00")
    assert report.missed == Decimal("10.00")
    assert report.utilization == 50
    assert report.range_label == "Year to date"
    assert report.remaining_this_year == Decimal("95.00")
    assert [row["total"] for row in report.month_rows] == [
        Decimal("10.00"), Decimal("0"), Decimal("5.00")
    ]


def test_partial_first_period_is_not_counted_as_missed_or_utilization(benefit_by_id):
    uber = benefit_by_id["uber"]
    rows = [make_txn("feb", "2026-02-10", 10, "Uber", "UBER")]

    report = build_report([uber], rows, date(2026, 3, 15), {"annual_fee": 325})

    assert report.captured == Decimal("10.00")
    assert report.available == Decimal("10.00")
    assert report.missed == Decimal("0")
    assert report.utilization == 0
    assert report.range_label == "Since Feb 10"


def test_semiannual_credit_is_charted_in_posting_month(benefit_by_id):
    resy = benefit_by_id["resy"]
    rows = [
        make_txn("coverage", "2026-01-01", 1, "Other", "OTHER"),
        make_txn("resy", "2026-04-20", -50, None, "AMEX RESY CREDIT"),
    ]

    report = build_report([resy], rows, date(2026, 8, 1), {"annual_fee": 325})

    april = next(row for row in report.month_rows if row["date"].month == 4)
    assert april["values"]["resy"] == Decimal("50.00")
    assert report.benefit_rows[0]["current_streak"] == 0
    assert report.benefit_rows[0]["longest_streak"] == 1


def test_gold_configuration_has_expected_annual_ceiling(benefits):
    rows = [make_txn("coverage", "2026-01-01", 1, "Other", "OTHER")]
    report = build_report(benefits, rows, date(2026, 1, 15), {"annual_fee": 325})

    assert report.annual_ceiling == Decimal("424.00")
    assert report.annual_fee == Decimal("325.00")
