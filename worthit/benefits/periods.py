import calendar
from datetime import date

from worthit.benefits.schema import BenefitConfig


def current_period(benefit: BenefitConfig, today: date) -> tuple[date, date]:
    if benefit.period == "monthly":
        start = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
    elif benefit.period == "semiannual_calendar":
        if today.month <= 6:
            start, end = date(today.year, 1, 1), date(today.year, 6, 30)
        else:
            start, end = date(today.year, 7, 1), date(today.year, 12, 31)
    else:
        raise ValueError(f"Unknown period type: {benefit.period}")
    return start, end


def days_remaining(period_end: date, today: date) -> int:
    return (period_end - today).days
