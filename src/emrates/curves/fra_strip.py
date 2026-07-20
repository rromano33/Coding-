"""FRA-strip short-end bootstrap for Czech/Poland/Hungary.

Their Tickers sheet includes a rolling FRA strip (SECURITY_DES like
"CZK FRA 1X4" = 3-month rate starting 1 month from spot, ending 4 months
from spot) used by the desk to trade the short end — the swap tickers
alone (CKSW1/PZSW1/HFSW1...) have nothing below 1Y.

FRA rates are simple/linear money-market rates over [start, end] measured
from spot (T+2), not zero rates from valuation_date, so they chain off
each other's discount factor rather than off valuation_date directly:
DF(end) = DF(start) / (1 + rate * tau(start, end)).
"""
from __future__ import annotations

import re
from datetime import date

from emrates.conventions.compounding import Compounding, discount_factor as _df_from_rate
from emrates.conventions.daycount import DayCount, year_fraction
from emrates.curves.base import DiscountCurve
from emrates.data.calendars import Calendar

_FRA_PATTERN = re.compile(r"(\d+)\s*[Xx]\s*(\d+)")


def parse_fra_period(security_des: str) -> tuple[int, int]:
    """'CZK FRA 1X4' -> (1, 4) — months forward from spot."""
    match = _FRA_PATTERN.search(security_des)
    if not match:
        raise ValueError(f"can't find an NxM period in {security_des!r}")
    return int(match.group(1)), int(match.group(2))


def month_offset(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, 28)
    return date(year, month, day)


def chain_from(anchor_month: int, periods: dict[int, tuple[int, float]]) -> list[tuple[int, int, float]]:
    """Greedily follows periods={start_month: (end_month, rate)} as far as it
    chains contiguously from anchor_month, e.g. {1:(4,r1),4:(7,r2),7:(10,r3)}
    starting at 1 -> [(1,4,r1),(4,7,r2),(7,10,r3)]."""
    chain = []
    month = anchor_month
    while month in periods:
        end_month, rate = periods[month]
        chain.append((month, end_month, rate))
        month = end_month
    return chain


def bootstrap_fra_chain(
    spot_date: date,
    anchor_date: date,
    anchor_df: float,
    anchor_months_from_spot: int,
    fra_chain: list[tuple[int, int, float]],
    calendar: Calendar,
) -> list[tuple[date, float]]:
    """fra_chain: [(start_month, end_month, rate), ...], already contiguous
    (see chain_from) and starting at anchor_months_from_spot. Returns
    [(date, discount_factor), ...] for each period end, chained off anchor_df."""
    results = []
    current_date, current_df, current_month = anchor_date, anchor_df, anchor_months_from_spot
    for start_month, end_month, rate in fra_chain:
        if start_month != current_month:
            raise ValueError(f"FRA chain gap: expected period starting at month {current_month}, got {start_month}")
        end_date = calendar.adjust_following(month_offset(spot_date, end_month))
        tau = year_fraction(current_date, end_date, DayCount.ACT_360, calendar)
        end_df = current_df / (1.0 + rate * tau)
        results.append((end_date, end_df))
        current_date, current_df, current_month = end_date, end_df, end_month
    return results


def extend_with_fra_strip(
    curve: DiscountCurve,
    spot_date: date,
    policy_rate: float,
    fra_data: list[tuple[int, int, float]],
    calendar: Calendar,
) -> DiscountCurve:
    """Splices a FRA-strip short end onto an existing swap-only curve: one
    chain from month 1 (anchored on the policy rate as a stub proxy for
    [valuation_date, spot+1M]) up to as far as the strip chains, and one
    chain from the curve's own first (shortest) pillar — assumed to be the
    1Y swap point the 12x15/15x18/... FRAs pick up from — onward."""
    periods = {start: (end, rate) for start, end, rate in fra_data}

    valuation_date = curve.valuation_date
    short_anchor_date = calendar.adjust_following(month_offset(spot_date, 1))
    short_anchor_tau = year_fraction(valuation_date, short_anchor_date, DayCount.ACT_360, calendar)
    short_anchor_df = _df_from_rate(policy_rate, short_anchor_tau, Compounding.EXPONENTIAL)
    short_chain = bootstrap_fra_chain(
        spot_date, short_anchor_date, short_anchor_df, 1, chain_from(1, periods), calendar
    )

    long_anchor_date, long_anchor_df = curve.pillar_dates[0], curve.discount_factors[0]
    long_anchor_month = round(year_fraction(spot_date, long_anchor_date, DayCount.ACT_360, calendar) * 12)
    long_chain = bootstrap_fra_chain(
        spot_date, long_anchor_date, long_anchor_df, long_anchor_month, chain_from(long_anchor_month, periods), calendar
    )

    combined = {d: df for d, df in zip(curve.pillar_dates, curve.discount_factors)}
    combined.update({d: df for d, df in short_chain + long_chain if d not in combined})
    sorted_dates = sorted(combined)
    return DiscountCurve(
        valuation_date, sorted_dates, [combined[d] for d in sorted_dates], curve.convention, curve.compounding, calendar
    )
