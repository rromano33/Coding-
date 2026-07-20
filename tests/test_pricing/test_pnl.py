from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.pricing.discounting import value_swap
from emrates.pricing.instruments import PayReceive, Swap
from emrates.pricing.pnl import decompose_pnl, roll_curve


def _curve(valuation_date, pillar_dates, rates):
    dfs = [(1 + r) ** (-((d - valuation_date).days / 365)) for d, r in zip(pillar_dates, rates)]
    return DiscountCurve(valuation_date, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_bullet_swap_at_par_has_zero_npv():
    valuation_date = date(2026, 1, 5)
    maturity = date(2027, 1, 5)
    curve = _curve(valuation_date, [maturity], [0.1075])

    swap = Swap(
        trade_id="T1",
        country="brazil",
        start_date=valuation_date,
        maturity_date=maturity,
        fixed_rate=0.1075,
        notional=1_000_000,
        pay_receive=PayReceive.RECEIVE,
    )
    assert value_swap(swap, curve) == pytest.approx(0.0, abs=1e-6)


def test_pnl_decomposition_sums_to_total():
    valuation_date = date(2026, 1, 5)
    maturity = date(2027, 6, 5)
    curve_t0 = _curve(valuation_date, [maturity], [0.10])

    later = date(2026, 2, 5)
    curve_t1 = _curve(later, [maturity], [0.105])  # curve moved up 50bp between t0 and t1

    swap = Swap(
        trade_id="T1",
        country="brazil",
        start_date=valuation_date,
        maturity_date=maturity,
        fixed_rate=0.10,
        notional=1_000_000,
        pay_receive=PayReceive.RECEIVE,
    )
    breakdown = decompose_pnl(swap, curve_t0, curve_t1)
    assert breakdown.carry + breakdown.curve_move == pytest.approx(breakdown.total, abs=1e-6)
    # receiving fixed and curve moved up (rates rose) -> should lose money on the curve-move leg
    assert breakdown.curve_move < 0


def test_roll_curve_preserves_forward_shape():
    valuation_date = date(2026, 1, 5)
    far = date(2028, 1, 5)
    curve = _curve(valuation_date, [far], [0.09])
    rolled = roll_curve(curve, date(2026, 7, 5))
    assert rolled.zero_rate(far) == pytest.approx(curve.forward_rate(date(2026, 7, 5), far), abs=1e-9)
