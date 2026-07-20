from datetime import date

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import Pillar, ParSwapCurveBuilder
from emrates.curves.fra_strip import chain_from, extend_with_fra_strip, month_offset, parse_fra_period
from emrates.data.calendars import Calendar


def test_parse_fra_period():
    assert parse_fra_period("CZK FRA 1X4") == (1, 4)
    assert parse_fra_period("PLN FRA12x15") == (12, 15)
    assert parse_fra_period("HUF FRA 21X24") == (21, 24)


def test_month_offset():
    assert month_offset(date(2026, 7, 22), 1) == date(2026, 8, 22)
    assert month_offset(date(2026, 7, 22), 6) == date(2027, 1, 22)
    assert month_offset(date(2026, 11, 30), 3) == date(2027, 2, 28)  # clamped, no Feb 30


def test_chain_from_stops_at_gap():
    periods = {1: (4, 0.01), 4: (7, 0.01), 7: (10, 0.01), 12: (15, 0.01)}
    assert chain_from(1, periods) == [(1, 4, 0.01), (4, 7, 0.01), (7, 10, 0.01)]
    assert chain_from(12, periods) == [(12, 15, 0.01)]
    assert chain_from(9, periods) == []  # no period starts at month 9


def test_extend_with_fra_strip_fills_short_end_and_matches_swap_pillars():
    calendar = Calendar("czech", holidays=set())
    valuation_date = date(2026, 7, 20)
    spot = date(2026, 7, 22)

    swap_pillars = [
        Pillar(maturity=date(2027, 7, 22), rate=0.036),
        Pillar(maturity=date(2028, 7, 22), rate=0.0355),
    ]
    swap_curve = ParSwapCurveBuilder(DayCount.ACT_360, Compounding.EXPONENTIAL, 6, calendar).build(
        valuation_date, swap_pillars
    )

    fra_data = [(1, 4, 0.0365), (4, 7, 0.0358), (7, 10, 0.0356), (12, 15, 0.0359)]
    extended = extend_with_fra_strip(swap_curve, spot, policy_rate=0.037, fra_data=fra_data, calendar=calendar)

    # the swap curve's own pillars must still be present (exact splice, not a re-bootstrap)
    assert date(2027, 7, 22) in extended.pillar_dates
    assert date(2028, 7, 22) in extended.pillar_dates
    # and the FRA chain added new, earlier pillars filling the short end
    assert len(extended.pillar_dates) > len(swap_curve.pillar_dates)
    assert min(extended.pillar_dates) < date(2027, 1, 1)
