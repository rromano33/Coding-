"""Swap valuation against a DiscountCurve.

Two cases, mirroring curves/base.py's two pillar styles:

- Bullet swaps (coupon_frequency_months is None — Brazil DI, Chile Cámara,
  Colombia IBR): single accrual at maturity on both legs, closed form.
- Periodic-coupon swaps (Mexico TIIE, South Africa JIBAR, Poland WIBOR,
  Czech PRIBOR, Hungary BUBOR): standard fixed-vs-floating leg valuation,
  floating leg via the single-curve telescoping identity
  PV_float = notional * (DF(start) - DF(maturity)).
"""
from __future__ import annotations

from emrates.curves.base import DiscountCurve
from emrates.conventions.schedule import generate_schedule
from emrates.pricing.instruments import PayReceive, Swap


def value_swap(swap: Swap, curve: DiscountCurve) -> float:
    """Net present value to the position holder (positive = position is in the money)."""
    df_start = curve.discount_factor(swap.start_date)
    df_maturity = curve.discount_factor(swap.maturity_date)

    if swap.coupon_frequency_months is None:
        tau = curve.tau(swap.start_date, swap.maturity_date)
        fixed_growth = (1.0 + swap.fixed_rate) ** tau
        npv_receive_fixed = swap.notional * (df_maturity * fixed_growth - df_start)
    else:
        schedule = generate_schedule(swap.start_date, swap.maturity_date, swap.coupon_frequency_months, curve.calendar)
        prior = [swap.start_date] + schedule[:-1]
        fixed_leg_pv = swap.notional * swap.fixed_rate * sum(
            curve.tau(p, d) * curve.discount_factor(d) for p, d in zip(prior, schedule)
        )
        floating_leg_pv = swap.notional * (df_start - df_maturity)
        npv_receive_fixed = fixed_leg_pv - floating_leg_pv

    return npv_receive_fixed if swap.pay_receive == PayReceive.RECEIVE else -npv_receive_fixed
