"""Coupon schedule generation, shared by curve bootstrap and swap valuation."""
from __future__ import annotations

import re
from datetime import date, timedelta

from emrates.data.calendars import Calendar


def tenor_to_date(valuation_date: date, tenor: str) -> date:
    """Parses market tenor strings like 'ON', '1M', '3M', '2Y' into a maturity date."""
    tenor = tenor.strip().upper()
    if tenor in ("ON", "O/N", "1D"):
        return valuation_date + timedelta(days=1)
    match = re.match(r"^(\d+)([DWMY])$", tenor)
    if not match:
        raise ValueError(f"unrecognized tenor format: {tenor!r}")
    n, unit = int(match.group(1)), match.group(2)
    year, month, day = valuation_date.year, valuation_date.month, valuation_date.day
    if unit == "D":
        return valuation_date + timedelta(days=n)
    if unit == "W":
        return valuation_date + timedelta(weeks=n)
    if unit == "M":
        month += n
    elif unit == "Y":
        year += n
    while month > 12:
        month -= 12
        year += 1
    day = min(day, 28)
    return date(year, month, day)


def generate_schedule(start: date, maturity: date, frequency_months: int, calendar: Calendar | None = None) -> list[date]:
    """Coupon dates from `start` to `maturity`, stepping backward from maturity
    in `frequency_months` increments (standard back-to-front swap schedule
    generation), business-day adjusted (modified following) if a calendar is given."""
    dates = []
    d = maturity
    while d > start:
        dates.append(d)
        year = d.year
        month = d.month - frequency_months
        while month <= 0:
            month += 12
            year -= 1
        day = min(d.day, 28)
        d = date(year, month, day)
    dates.reverse()
    if calendar is not None:
        dates = [calendar.adjust_modified_following(dd) for dd in dates]
    return dates
