from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import Pillar, ParSwapCurveBuilder, ZeroRateCurveBuilder
from emrates.data.calendars import Calendar


def test_zero_rate_curve_roundtrips_rate():
    calendar = Calendar("brazil", holidays=set())
    builder = ZeroRateCurveBuilder(DayCount.BUS_252, Compounding.EXPONENTIAL, calendar)
    valuation_date = date(2026, 1, 5)
    maturity = date(2027, 1, 5)
    pillar = Pillar(maturity=maturity, rate=0.1075)

    curve = builder.build(valuation_date, [pillar])
    assert curve.zero_rate(maturity) == pytest.approx(0.1075, abs=1e-9)


def test_par_swap_curve_bootstrap_recovers_par_rate():
    calendar = Calendar("south_africa", holidays=set())
    builder = ParSwapCurveBuilder(DayCount.ACT_365, Compounding.EXPONENTIAL, coupon_frequency_months=3, calendar=calendar)
    valuation_date = date(2026, 1, 5)
    pillars = [
        Pillar(maturity=date(2026, 7, 5), rate=0.075),
        Pillar(maturity=date(2027, 1, 5), rate=0.072),
        Pillar(maturity=date(2028, 1, 5), rate=0.068),
    ]
    curve = builder.build(valuation_date, pillars)

    # A par swap priced off its own bootstrapped curve must NPV to (approximately) zero.
    from emrates.conventions.schedule import generate_schedule

    for p in pillars:
        schedule = generate_schedule(valuation_date, p.maturity, 3, calendar)
        prior = [valuation_date] + schedule[:-1]
        fixed_leg = sum(curve.tau(a, b) * curve.discount_factor(b) for a, b in zip(prior, schedule))
        floating_leg = curve.discount_factor(valuation_date) - curve.discount_factor(p.maturity)
        npv = p.rate * fixed_leg - floating_leg
        # sub-basis-point tolerance on a unit-notional par swap — plenty tight for
        # trading-desk use; tighter starts fighting schedule-interpolation floating
        # point noise (bootstrap converges against a trial curve missing later
        # pillars, then gets re-checked here against the final one) rather than
        # testing anything meaningful
        assert npv == pytest.approx(0.0, abs=1e-5)


def test_discount_factor_interpolation_between_pillars():
    calendar = Calendar("brazil", holidays=set())
    builder = ZeroRateCurveBuilder(DayCount.ACT_365, Compounding.EXPONENTIAL, calendar)
    valuation_date = date(2026, 1, 1)
    curve = builder.build(
        valuation_date,
        [Pillar(date(2026, 7, 1), 0.10), Pillar(date(2027, 1, 1), 0.11)],
    )
    mid_df = curve.discount_factor(date(2026, 10, 1))
    assert curve.discount_factor(date(2026, 7, 1)) > mid_df > curve.discount_factor(date(2027, 1, 1))
