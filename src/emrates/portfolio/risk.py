"""DV01 and PnL attribution across a book of positions."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from emrates.conventions.compounding import discount_factor as _df_from_rate
from emrates.curves.base import DiscountCurve
from emrates.pricing.discounting import value_swap
from emrates.pricing.instruments import Swap
from emrates.pricing.pnl import PnlBreakdown, decompose_pnl


def dv01(swap: Swap, curve: DiscountCurve, bump_bps: float = 1.0) -> float:
    """NPV change for a 1bp parallel bump to the curve's zero rates, per position."""
    bumped_dfs = []
    for d in curve.pillar_dates:
        tau = curve.tau(curve.valuation_date, d)
        z = curve.zero_rate(d) + bump_bps / 1e4
        bumped_dfs.append(_df_from_rate(z, tau, curve.compounding))

    bumped_curve = DiscountCurve(
        curve.valuation_date, curve.pillar_dates, bumped_dfs, curve.convention, curve.compounding, curve.calendar
    )
    return value_swap(swap, bumped_curve) - value_swap(swap, curve)


@dataclass
class PositionRisk:
    trade_id: str
    country: str
    dv01: float
    pnl: PnlBreakdown


def book_risk(positions: list[Swap], curves_t0: dict[str, DiscountCurve], curves_t1: dict[str, DiscountCurve]) -> pd.DataFrame:
    rows = []
    for swap in positions:
        curve_t0 = curves_t0[swap.country]
        curve_t1 = curves_t1[swap.country]
        pnl = decompose_pnl(swap, curve_t0, curve_t1)
        rows.append(
            {
                "trade_id": swap.trade_id,
                "country": swap.country,
                "dv01": dv01(swap, curve_t1),
                "pnl_total": pnl.total,
                "pnl_carry": pnl.carry,
                "pnl_curve_move": pnl.curve_move,
            }
        )
    return pd.DataFrame(rows)
