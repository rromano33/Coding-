"""PnL for an open position between two dates, split into carry/roll-down
(pure time decay, forward curve shape held constant) and curve move
(everything else)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from emrates.curves.base import DiscountCurve
from emrates.pricing.discounting import value_swap
from emrates.pricing.instruments import Swap


def roll_curve(curve: DiscountCurve, new_valuation_date: date) -> DiscountCurve:
    """Same forward-rate curve, re-based to a later valuation date — i.e. what the
    curve implied yesterday would look like today if nothing moved but time."""
    base_df = curve.discount_factor(new_valuation_date)
    new_dates = [d for d in curve.pillar_dates if d > new_valuation_date]
    new_dfs = [curve.discount_factor(d) / base_df for d in new_dates]
    return DiscountCurve(new_valuation_date, new_dates, new_dfs, curve.convention, curve.compounding, curve.calendar)


@dataclass
class PnlBreakdown:
    total: float
    carry: float
    curve_move: float


def decompose_pnl(swap: Swap, curve_t0: DiscountCurve, curve_t1: DiscountCurve) -> PnlBreakdown:
    npv_t0 = value_swap(swap, curve_t0)
    rolled = roll_curve(curve_t0, curve_t1.valuation_date)
    npv_rolled = value_swap(swap, rolled)
    npv_t1 = value_swap(swap, curve_t1)

    carry = npv_rolled - npv_t0
    curve_move = npv_t1 - npv_rolled
    return PnlBreakdown(total=npv_t1 - npv_t0, carry=carry, curve_move=curve_move)
