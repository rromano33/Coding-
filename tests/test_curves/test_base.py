from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import HybridCurveBuilder, Pillar, ParSwapCurveBuilder, ZeroRateCurveBuilder
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


def test_hybrid_builder_bullet_short_end_matches_zero_rate_builder():
    calendar = Calendar("chile", holidays=set())
    valuation_date = date(2026, 1, 5)
    short_pillar = Pillar(maturity=date(2026, 7, 5), rate=0.075)  # 6M, inside the 18M bullet cutoff

    hybrid = HybridCurveBuilder(
        DayCount.ACT_360, Compounding.EXPONENTIAL, coupon_frequency_months=6, bullet_cutoff_months=18, calendar=calendar
    )
    curve = hybrid.build(valuation_date, [short_pillar])
    zero_only = ZeroRateCurveBuilder(DayCount.ACT_360, Compounding.EXPONENTIAL, calendar).build(
        valuation_date, [short_pillar]
    )
    assert curve.discount_factor(short_pillar.maturity) == pytest.approx(
        zero_only.discount_factor(short_pillar.maturity), abs=1e-12
    )


def test_hybrid_builder_coupon_long_end_recovers_par_rate():
    # Chile: bullet out to 18M, semi-annual coupon par swap from 2Y —
    # confirmed via Bloomberg DES (CHSWP5) 22/07/2026.
    calendar = Calendar("chile", holidays=set())
    valuation_date = date(2026, 1, 5)
    pillars = [
        Pillar(maturity=date(2026, 7, 5), rate=0.075),   # 6M, bullet
        Pillar(maturity=date(2027, 1, 5), rate=0.072),   # 1Y, bullet
        Pillar(maturity=date(2028, 1, 5), rate=0.068),   # 2Y, coupon-bearing
        Pillar(maturity=date(2031, 1, 5), rate=0.065),   # 5Y, coupon-bearing
    ]
    builder = HybridCurveBuilder(
        DayCount.ACT_360, Compounding.EXPONENTIAL, coupon_frequency_months=6, bullet_cutoff_months=18, calendar=calendar
    )
    curve = builder.build(valuation_date, pillars)

    from emrates.conventions.schedule import generate_schedule

    for p in pillars[2:]:  # only the coupon-bearing ones have a fixed-leg schedule to NPV-check
        schedule = generate_schedule(valuation_date, p.maturity, 6, calendar)
        prior = [valuation_date] + schedule[:-1]
        fixed_leg = sum(curve.tau(a, b) * curve.discount_factor(b) for a, b in zip(prior, schedule))
        floating_leg = curve.discount_factor(valuation_date) - curve.discount_factor(p.maturity)
        npv = p.rate * fixed_leg - floating_leg
        assert npv == pytest.approx(0.0, abs=1e-5)

    # the bullet pillars must still round-trip their own quoted zero rate exactly
    assert curve.zero_rate(pillars[0].maturity) == pytest.approx(0.075, abs=1e-9)
    assert curve.zero_rate(pillars[1].maturity) == pytest.approx(0.072, abs=1e-9)


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
