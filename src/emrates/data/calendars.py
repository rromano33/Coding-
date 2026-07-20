"""Business-day calendars, one per country, built from the 'Dates' sheet."""
from __future__ import annotations

from datetime import date, timedelta


class Calendar:
    def __init__(self, country: str, holidays: set[date]):
        self.country = country
        self.holidays = holidays

    def is_business_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def business_days_between(self, start: date, end: date) -> int:
        """Number of business days strictly between two dates (start exclusive, end inclusive),
        matching the B3 DI convention of 'dias úteis' between two dates."""
        if end < start:
            raise ValueError(f"end {end} precedes start {start}")
        n = 0
        d = start + timedelta(days=1)
        while d <= end:
            if self.is_business_day(d):
                n += 1
            d += timedelta(days=1)
        return n

    def add_business_days(self, d: date, n: int) -> date:
        step = 1 if n >= 0 else -1
        remaining = abs(n)
        cur = d
        while remaining > 0:
            cur += timedelta(days=step)
            if self.is_business_day(cur):
                remaining -= 1
        return cur

    def adjust_following(self, d: date) -> date:
        cur = d
        while not self.is_business_day(cur):
            cur += timedelta(days=1)
        return cur

    def adjust_modified_following(self, d: date) -> date:
        adjusted = self.adjust_following(d)
        if adjusted.month != d.month:
            cur = d
            while not self.is_business_day(cur):
                cur -= timedelta(days=1)
            return cur
        return adjusted


class CalendarSet:
    """Holds one Calendar per country, keyed by the country code used in config/countries/*.yaml."""

    def __init__(self, calendars: dict[str, Calendar]):
        self._calendars = calendars

    def __getitem__(self, country: str) -> Calendar:
        try:
            return self._calendars[country]
        except KeyError as exc:
            raise KeyError(
                f"no calendar loaded for '{country}' — check the 'Dates' sheet has a holiday column for it"
            ) from exc

    @classmethod
    def from_holiday_frame(cls, holidays_by_country: dict[str, list[date]]) -> "CalendarSet":
        return cls({country: Calendar(country, set(dates)) for country, dates in holidays_by_country.items()})
