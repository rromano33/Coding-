"""Thin accessor over the meeting-date calendars loaded from Input_BCs.xlsx."""
from __future__ import annotations

from datetime import date


def upcoming_meetings(all_meetings: list[date], valuation_date: date, horizon: int | None = None) -> list[date]:
    future = sorted(d for d in all_meetings if d > valuation_date)
    return future[:horizon] if horizon else future
