from datetime import date

from worthit.benefits.periods import current_period, days_remaining
from worthit.benefits.schema import BenefitConfig, MatchRule


def _benefit(period):
    return BenefitConfig(
        id="test",
        label="Test",
        amount=10.0,
        period=period,
        detection_mode="credit_match",
        match=MatchRule(),
    )


def test_monthly_period_mid_month():
    b = _benefit("monthly")
    start, end = current_period(b, date(2026, 6, 15))
    assert start == date(2026, 6, 1)
    assert end == date(2026, 6, 30)


def test_monthly_period_december_rollover():
    b = _benefit("monthly")
    start, end = current_period(b, date(2026, 12, 25))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)


def test_monthly_period_february_leap_year():
    b = _benefit("monthly")
    start, end = current_period(b, date(2028, 2, 10))
    assert start == date(2028, 2, 1)
    assert end == date(2028, 2, 29)


def test_monthly_period_february_non_leap_year():
    b = _benefit("monthly")
    start, end = current_period(b, date(2026, 2, 10))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_semiannual_first_half():
    b = _benefit("semiannual_calendar")
    start, end = current_period(b, date(2026, 3, 1))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 6, 30)


def test_semiannual_second_half():
    b = _benefit("semiannual_calendar")
    start, end = current_period(b, date(2026, 7, 1))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 12, 31)


def test_semiannual_boundary_june_30():
    b = _benefit("semiannual_calendar")
    start, end = current_period(b, date(2026, 6, 30))
    assert (start, end) == (date(2026, 1, 1), date(2026, 6, 30))


def test_semiannual_boundary_july_1():
    b = _benefit("semiannual_calendar")
    start, end = current_period(b, date(2026, 7, 1))
    assert (start, end) == (date(2026, 7, 1), date(2026, 12, 31))


def test_days_remaining():
    assert days_remaining(date(2026, 6, 30), date(2026, 6, 25)) == 5
    assert days_remaining(date(2026, 6, 30), date(2026, 6, 30)) == 0
