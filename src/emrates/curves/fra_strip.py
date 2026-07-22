"""FRA-strip short-end bootstrap for Czech/Poland/Hungary.

Their Tickers sheet includes a rolling FRA strip (SECURITY_DES like
"CZK FRA 1X4" = 3-month rate starting 1 month from spot, ending 4 months
from spot) used by the desk to trade the short end — the swap tickers
alone (CKSW1/PZSW1/HFSW1...) have nothing below 1Y.

FRA rates are simple/linear money-market rates over [start, end] measured
from spot (T+2), not zero rates from valuation_date, so they chain off
each other's discount factor rather than off valuation_date directly:
DF(end) = DF(start) / (1 + rate * tau(start, end)).

Dates are reconstructed here (month_offset + business-day roll), not read
from Bloomberg — checked via scripts/inspect_fra_fields.py (22/07/2026):
every candidate date field (END_ACCRUAL_DT, FLT_START_DT/FLT_END_DT,
FWD_START_DATE/FWD_END_DATE, START_ACCRUAL_DT, FIRST_SETTLE_DT, ...) comes
back NaN for these tickers, and the one field that IS populated,
SETTLE_DT, is identical (the spot date itself) across every single FRA —
these "CMPN Curncy" tickers are quoted relative to *today's* spot,
recomputed daily, so Bloomberg has no fixed date to store for them. The
business-day roll uses Modified Following (adjust_modified_following, not
plain adjust_following) — the standard IRS/FRA market convention: roll
forward, unless that crosses into the next calendar month, in which case
roll backward instead. Plain Following can push a period boundary into a
month the FRA was never meant to reach.
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


def best_chain_start(periods: dict[int, tuple[int, float]], cap_month: int) -> tuple[int | None, list[tuple[int, int, float]]]:
    """A real rolling FRA strip (1X4, 2X5, 3X6, 4X7, 5X8, 6X9, 7X10, 8X11,
    9X12, 12X15, ...) has several different starting months that each chain
    contiguously (1->4->7->10, or 2->5->8->11, or 3->6->9->12->...) — they
    are NOT redundant, each uses a disjoint subset of the real quotes, and
    they reach different distances. Picking a fixed starting month (e.g.
    always 1) can strand most of the strip's real data and short of the
    point (cap_month, e.g. the swap curve's own first pillar) it needs to
    reach — in the exact period layout above, starting at 1 only reaches
    month 10 using 3 quotes, while starting at 3 reaches all the way to 24
    using 7. This tries every available starting month and keeps whichever
    contiguous chain (capped so it never overshoots cap_month, where the
    swap-quoted curve takes over) reaches farthest."""
    best_start: int | None = None
    best_chain: list[tuple[int, int, float]] = []
    for start in sorted(periods):
        if start > cap_month:
            continue
        chain: list[tuple[int, int, float]] = []
        month = start
        while month in periods:
            end_month, rate = periods[month]
            if end_month > cap_month:
                break
            chain.append((month, end_month, rate))
            month = end_month
        if chain and chain[-1][1] > (best_chain[-1][1] if best_chain else -1):
            best_start, best_chain = start, chain
    return best_start, best_chain


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
        end_date = calendar.adjust_modified_following(month_offset(spot_date, end_month))
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
    """Splices a FRA-strip short end onto an existing swap-only curve: the
    best-reaching chain the strip offers (see best_chain_start — anchored on
    the policy rate as a stub proxy for [valuation_date, spot+start_month])
    up to the curve's own first (shortest) pillar, assumed to be the 1Y swap
    point the 12x15/15x18/... FRAs pick up from — plus a second chain from
    that pillar onward."""
    periods = {start: (end, rate) for start, end, rate in fra_data}
    valuation_date = curve.valuation_date

    long_anchor_date, long_anchor_df = curve.pillar_dates[0], curve.discount_factors[0]
    long_anchor_month = round(year_fraction(spot_date, long_anchor_date, DayCount.ACT_360, calendar) * 12)

    short_start, short_periods = best_chain_start(periods, long_anchor_month)
    if short_start is None:
        short_chain = []
    else:
        short_anchor_date = calendar.adjust_modified_following(month_offset(spot_date, short_start))
        short_anchor_tau = year_fraction(valuation_date, short_anchor_date, DayCount.ACT_360, calendar)
        short_anchor_df = _df_from_rate(policy_rate, short_anchor_tau, Compounding.EXPONENTIAL)
        short_chain = bootstrap_fra_chain(
            spot_date, short_anchor_date, short_anchor_df, short_start, short_periods, calendar
        )

    long_chain = bootstrap_fra_chain(
        spot_date, long_anchor_date, long_anchor_df, long_anchor_month, chain_from(long_anchor_month, periods), calendar
    )

    combined = {d: df for d, df in zip(curve.pillar_dates, curve.discount_factors)}
    combined.update({d: df for d, df in short_chain + long_chain if d not in combined})
    sorted_dates = sorted(combined)
    return DiscountCurve(
        valuation_date, sorted_dates, [combined[d] for d in sorted_dates], curve.convention, curve.compounding, calendar
    )
