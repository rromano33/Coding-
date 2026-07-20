from datetime import date

import pytest

from emrates.central_banks.stripper import strip_meeting_path
from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve


def _flat_curve(valuation_date, flat_rate, pillar_dates):
    dfs = [(1 + flat_rate) ** (-((d - valuation_date).days / 365)) for d in pillar_dates]
    return DiscountCurve(valuation_date, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_flat_curve_prices_no_hikes_or_cuts():
    valuation_date = date(2026, 1, 5)
    meetings = [date(2026, 3, 1), date(2026, 4, 15), date(2026, 6, 1)]
    curve = _flat_curve(valuation_date, 0.10, meetings)

    result = strip_meeting_path(curve, meetings, current_policy_rate=0.10)
    assert len(result) == 2  # last meeting dropped: no 'after' period defined
    for r in result:
        assert r.implied_change_bps == pytest.approx(0.0, abs=1e-6)


def test_cumulative_matches_sum_of_implied_changes_even_if_policy_rate_ticker_disagrees_with_stub():
    # current_policy_rate comes from a separate Bloomberg ticker than the curve
    # itself, so it never matches the curve's own spot->first-meeting stub rate
    # exactly. cumulative_change_from_spot_bps must still tie out to the sum of
    # the displayed implied_change_bps column (a flat curve prices zero hikes,
    # regardless of what current_policy_rate says).
    valuation_date = date(2026, 1, 5)
    meetings = [date(2026, 3, 1), date(2026, 4, 15), date(2026, 6, 1)]
    curve = _flat_curve(valuation_date, 0.12, meetings)

    result = strip_meeting_path(curve, meetings, current_policy_rate=0.05)
    running = 0.0
    for r in result:
        running += r.implied_change_bps
        assert r.cumulative_change_from_spot_bps == pytest.approx(running, abs=1e-6)
        assert r.cumulative_change_from_spot_bps == pytest.approx(0.0, abs=1e-6)


def test_curve_pricing_a_hike_shows_positive_change():
    valuation_date = date(2026, 1, 5)
    meeting_1 = date(2026, 3, 1)
    meeting_2 = date(2026, 4, 15)
    # rate steps up sharply after meeting_1 relative to before it
    dfs = []
    for d, r in [(meeting_1, 0.10), (meeting_2, 0.115)]:
        dfs.append((1 + r) ** (-((d - valuation_date).days / 365)))
    curve = DiscountCurve(valuation_date, [meeting_1, meeting_2], dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)

    result = strip_meeting_path(curve, [meeting_1, meeting_2], current_policy_rate=0.10)
    assert len(result) == 1
    assert result[0].implied_change_bps > 0
