"""Year-fraction conventions used across the EM rates curves.

BUS_252 counts business days (not calendar days) and needs a calendar —
it is the Brazilian market standard (DI futures, CDI swaps) and is what
makes Brazil's exponential compounding land on whole-percent annualized
rates. The other conventions are calendar-day based and only need the
raw dates.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from emrates.data.calendars import Calendar


class DayCount(str, Enum):
    BUS_252 = "BUS/252"
    ACT_360 = "ACT/360"
    ACT_365 = "ACT/365"


def year_fraction(start: date, end: date, convention: DayCount, calendar: Calendar | None = None) -> float:
    if end < start:
        raise ValueError(f"end date {end} precedes start date {start}")

    if convention == DayCount.BUS_252:
        if calendar is None:
            raise ValueError("BUS/252 requires a Calendar to count business days")
        return calendar.business_days_between(start, end) / 252.0
    if convention == DayCount.ACT_360:
        return (end - start).days / 360.0
    if convention == DayCount.ACT_365:
        return (end - start).days / 365.0
    raise ValueError(f"unknown day count convention: {convention}")
