from datetime import date

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import Pillar, ZeroRateCurveBuilder
from emrates.curves.nss import fit_nss_curve
from emrates.data.calendars import Calendar


def test_nss_smooths_short_window_forward_far_from_valuation():
    """Regression test for the exact bug found comparing against Bloomberg's
    CDIE screen: a real DI1 curve has small pillar-to-pillar zigzags, and
    extracting a forward rate over a short window far from today amplifies
    that zigzag by roughly t_start/(t_end-t_start). Any *exact* interpolation
    (log-linear, monotone cubic, whatever) inherits this; only a genuine
    smoothed fit like NSS removes it."""
    calendar = Calendar("brazil", holidays=set())
    valuation_date = date(2026, 7, 20)

    # a realistic, mostly-smooth ~14% DI curve with one small zigzag typical
    # of real market prints (13.98 dips then 14.035 recovers, a few bps)
    data = [
        (date(2026, 8, 3), 14.153), (date(2026, 9, 1), 14.033), (date(2026, 10, 1), 13.971),
        (date(2026, 11, 3), 13.94), (date(2026, 12, 1), 13.93), (date(2027, 1, 4), 13.935),
        (date(2027, 2, 1), 13.975), (date(2027, 3, 1), 14.0), (date(2027, 4, 1), 14.0),
        (date(2027, 5, 3), 13.98), (date(2027, 6, 1), 14.035), (date(2027, 7, 1), 14.07),
        (date(2027, 8, 2), 14.09), (date(2027, 10, 1), 14.115), (date(2027, 11, 1), 14.12),
        (date(2027, 12, 1), 14.09), (date(2028, 1, 3), 14.14), (date(2028, 4, 3), 14.195),
    ]
    pillars = [Pillar(maturity=m, rate=r / 100) for m, r in data]
    exact_curve = ZeroRateCurveBuilder(DayCount.BUS_252, Compounding.EXPONENTIAL, calendar).build(
        valuation_date, pillars
    )
    smoothed_curve = fit_nss_curve(exact_curve)

    window_start, window_end = date(2027, 4, 29), date(2027, 6, 17)
    exact_change_bps = exact_curve.forward_rate(window_start, window_end) * 1e4
    smoothed_change_bps = smoothed_curve.forward_rate(window_start, window_end) * 1e4

    # this exact window is the one that blew up to ~1448bps on the unsmoothed
    # curve (vs ~1400bps neighbors) during the original investigation
    assert exact_change_bps > 1440
    assert 1380 < smoothed_change_bps < 1430


def test_nss_reproduces_pillars_reasonably_well():
    """NSS deliberately doesn't hit every pillar exactly (that's the point —
    it trades exact fit for smoothness) but it shouldn't be wildly off either."""
    calendar = Calendar("brazil", holidays=set())
    valuation_date = date(2026, 7, 20)
    pillars = [
        Pillar(maturity=date(2026, 10, 1), rate=0.14),
        Pillar(maturity=date(2027, 1, 1), rate=0.1405),
        Pillar(maturity=date(2027, 7, 1), rate=0.141),
        Pillar(maturity=date(2028, 1, 1), rate=0.1415),
        Pillar(maturity=date(2029, 1, 1), rate=0.142),
    ]
    exact_curve = ZeroRateCurveBuilder(DayCount.BUS_252, Compounding.EXPONENTIAL, calendar).build(
        valuation_date, pillars
    )
    smoothed_curve = fit_nss_curve(exact_curve)

    for p in pillars:
        exact_zero = exact_curve.zero_rate(p.maturity)
        tau = smoothed_curve.tau(valuation_date, p.maturity)
        smoothed_df = smoothed_curve.discount_factor(p.maturity)
        smoothed_zero = smoothed_df ** (-1 / tau) - 1
        assert abs(smoothed_zero - exact_zero) < 0.002  # within 20bps
