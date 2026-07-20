from datetime import date

import pytest

from emrates.conventions.daycount import DayCount, year_fraction
from emrates.data.calendars import Calendar


def test_act_360():
    tau = year_fraction(date(2026, 1, 1), date(2026, 7, 1), DayCount.ACT_360)
    assert tau == pytest.approx(181 / 360)


def test_act_365():
    tau = year_fraction(date(2026, 1, 1), date(2027, 1, 1), DayCount.ACT_365)
    assert tau == pytest.approx(365 / 365)


def test_bus_252_counts_only_business_days():
    calendar = Calendar("brazil", holidays=set())
    # 2026-01-05 (Mon) to 2026-01-09 (Fri): 4 business days between them
    tau = year_fraction(date(2026, 1, 5), date(2026, 1, 9), DayCount.BUS_252, calendar)
    assert tau == pytest.approx(4 / 252)


def test_bus_252_requires_calendar():
    with pytest.raises(ValueError):
        year_fraction(date(2026, 1, 1), date(2026, 1, 2), DayCount.BUS_252)
