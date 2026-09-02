import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from worthit.benefits import matcher
from worthit.benefits.schema import BenefitConfig


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _cap(benefit: BenefitConfig) -> Decimal:
    return _money(benefit.amount_cap if benefit.amount_cap is not None else benefit.amount)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)


def _periods(benefit: BenefitConfig, start: date, end: date):
    cursor = _month_start(start)
    if benefit.period == "semiannual_calendar":
        cursor = date(start.year, 1 if start.month <= 6 else 7, 1)
    while cursor <= end:
        if benefit.period == "monthly":
            period_end = cursor.replace(day=calendar.monthrange(cursor.year, cursor.month)[1])
            next_start = _next_month(cursor)
        else:
            period_end = date(cursor.year, 6, 30) if cursor.month == 1 else date(cursor.year, 12, 31)
            next_start = date(cursor.year, 7, 1) if cursor.month == 1 else date(cursor.year + 1, 1, 1)
        yield cursor, period_end
        cursor = next_start


def _used(benefit: BenefitConfig, rows: list) -> Decimal:
    if benefit.detection_mode == "spend_threshold":
        total = sum((_money(row["amount"]) for row in rows), Decimal("0"))
    else:
        total = sum((abs(_money(row["amount"])) for row in rows), Decimal("0"))
    return min(total, _cap(benefit))


@dataclass
class AnalyticsReport:
    range_key: str
    range_label: str
    start: date
    end: date
    coverage_start: date | None
    captured: Decimal
    available: Decimal
    missed: Decimal
    utilization: int
    annual_fee: Decimal
    fee_recovery: int
    annual_ceiling: Decimal
    remaining_this_year: Decimal
    projected_value: Decimal | None
    best_month: str | None
    month_rows: list[dict]
    benefit_rows: list[dict]
    ytd_complete: bool


def build_report(
    benefits: list[BenefitConfig],
    transactions: list,
    today: date,
    settings: dict,
    range_key: str = "ytd",
) -> AnalyticsReport:
    range_key = range_key if range_key in {"ytd", "12m", "all"} else "ytd"
    dates = [date.fromisoformat(row["date"]) for row in transactions if row["date"] <= today.isoformat()]
    coverage_start = min(dates) if dates else None

    if range_key == "ytd":
        requested_start = date(today.year, 1, 1)
    elif range_key == "12m":
        requested_start = _month_start(today)
        for _ in range(11):
            requested_start = (requested_start - timedelta(days=1)).replace(day=1)
    else:
        requested_start = coverage_start or date(today.year, 1, 1)

    start = max(requested_start, coverage_start) if coverage_start else requested_start
    ytd_complete = bool(coverage_start and coverage_start <= date(today.year, 1, 1))
    if range_key == "ytd":
        range_label = "Year to date" if ytd_complete else (f"Since {coverage_start.strftime('%b %-d')}" if coverage_start else "Year to date")
    elif range_key == "12m":
        range_label = "Last 12 months" if coverage_start and coverage_start <= requested_start else (f"Since {coverage_start.strftime('%b %-d, %Y')}" if coverage_start else "Last 12 months")
    else:
        range_label = "All history"

    month_starts = []
    cursor = _month_start(start)
    while cursor <= today:
        month_starts.append(cursor)
        cursor = _next_month(cursor)
    monthly = {month: {b.id: Decimal("0") for b in benefits} for month in month_starts}
    benefit_totals = {
        b.id: {"captured": Decimal("0"), "measured_captured": Decimal("0"), "available": Decimal("0"), "missed": Decimal("0"), "used_periods": [], "eligible_periods": 0}
        for b in benefits
    }

    for benefit in benefits:
        cap = _cap(benefit)
        for period_start, period_end in _periods(benefit, start, today):
            observed_start = max(period_start, start)
            observed_end = min(period_end, today)
            rows = matcher.match_transactions(benefit, transactions, observed_start, observed_end)
            used = _used(benefit, rows)
            fully_observed = bool(coverage_start and coverage_start <= period_start)
            if fully_observed:
                benefit_totals[benefit.id]["measured_captured"] += used
                benefit_totals[benefit.id]["available"] += cap
                benefit_totals[benefit.id]["eligible_periods"] += 1
                benefit_totals[benefit.id]["used_periods"].append(used >= cap)
                if period_end < today:
                    benefit_totals[benefit.id]["missed"] += max(Decimal("0"), cap - used)
            benefit_totals[benefit.id]["captured"] += used

            remaining = used
            for row in sorted(rows, key=lambda item: item["date"]):
                if remaining <= 0:
                    break
                value = _money(row["amount"] if benefit.detection_mode == "spend_threshold" else abs(row["amount"]))
                value = min(value, remaining)
                month = date.fromisoformat(row["date"]).replace(day=1)
                if month in monthly:
                    monthly[month][benefit.id] += value
                remaining -= value

    captured = sum((v["captured"] for v in benefit_totals.values()), Decimal("0"))
    available = sum((v["available"] for v in benefit_totals.values()), Decimal("0"))
    missed = sum((v["missed"] for v in benefit_totals.values()), Decimal("0"))
    measured_captured = sum(
        (v["measured_captured"] for v in benefit_totals.values()), Decimal("0")
    )
    utilization = round(float(measured_captured / available * 100)) if available else 0
    annual_fee = _money(settings.get("annual_fee", 325))
    fee_recovery = min(round(float(captured / annual_fee * 100)), 999) if annual_fee else 0
    annual_ceiling = sum(
        (_cap(b) * (12 if b.period == "monthly" else 2) for b in benefits), Decimal("0")
    )
    remaining_this_year = Decimal("0")
    for benefit in benefits:
        current_start, _ = next(_periods(benefit, today, today))
        current_used = _used(
            benefit, matcher.match_transactions(benefit, transactions, current_start, today)
        )
        remaining_this_year += max(Decimal("0"), _cap(benefit) - current_used)
        future_periods = (12 - today.month) if benefit.period == "monthly" else (1 if today.month <= 6 else 0)
        remaining_this_year += _cap(benefit) * future_periods

    completed_available = available - sum(
        (_cap(b) for b in benefits if coverage_start and coverage_start <= next(_periods(b, today, today))[0]),
        Decimal("0"),
    )
    completed_captured = max(Decimal("0"), measured_captured - sum(
        (_used(b, matcher.match_transactions(b, transactions, next(_periods(b, today, today))[0], today))
         for b in benefits if coverage_start and coverage_start <= next(_periods(b, today, today))[0]),
        Decimal("0"),
    ))
    projected = None
    if completed_available > 0:
        projected = _money(annual_ceiling * completed_captured / completed_available)

    month_rows = []
    for month in month_starts:
        values = monthly[month]
        total = sum(values.values(), Decimal("0"))
        month_rows.append({"date": month, "label": month.strftime("%b '%y"), "values": values, "total": total})
    max_month = max((row["total"] for row in month_rows), default=Decimal("0"))
    for row in month_rows:
        row["percent"] = float(row["total"] / max_month * 100) if max_month else 0
    best = max(month_rows, key=lambda row: row["total"], default=None)

    benefit_rows = []
    for benefit in benefits:
        values = benefit_totals[benefit.id]
        periods = values["used_periods"]
        current_streak = 0
        for complete in reversed(periods):
            if not complete:
                break
            current_streak += 1
        longest = run = 0
        for complete in periods:
            run = run + 1 if complete else 0
            longest = max(longest, run)
        rate = round(float(values["measured_captured"] / values["available"] * 100)) if values["available"] else 0
        benefit_rows.append({
            "id": benefit.id,
            "label": benefit.label,
            "captured": values["measured_captured"],
            "available": values["available"],
            "missed": values["missed"],
            "utilization": min(rate, 100),
            "current_streak": current_streak,
            "longest_streak": longest,
            "inferred": benefit.detection_mode == "spend_threshold",
        })

    return AnalyticsReport(
        range_key=range_key, range_label=range_label, start=start, end=today,
        coverage_start=coverage_start, captured=captured, available=available,
        missed=missed, utilization=min(utilization, 100), annual_fee=annual_fee,
        fee_recovery=fee_recovery, annual_ceiling=annual_ceiling,
        remaining_this_year=remaining_this_year, projected_value=projected,
        best_month=best["label"] if best and best["total"] else None,
        month_rows=month_rows, benefit_rows=benefit_rows, ytd_complete=ytd_complete,
    )
