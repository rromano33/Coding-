from datetime import date

import pytest

from emrates.central_banks.stripper import strip_meeting_path, strip_meeting_path_from_pillars
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


def _curve_from_rates(valuation_date, pillar_rates: dict) -> DiscountCurve:
    pillar_dates = sorted(pillar_rates)
    dfs = [(1 + pillar_rates[d]) ** (-((d - valuation_date).days / 365)) for d in pillar_dates]
    return DiscountCurve(valuation_date, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_strip_from_pillars_flat_curve_prices_nothing():
    valuation_date = date(2026, 1, 5)
    pillars = [date(2026, 6, 1), date(2027, 1, 5)]
    curve = _curve_from_rates(valuation_date, {p: 0.10 for p in pillars})
    meetings = [date(2026, 3, 1), date(2026, 4, 15)]  # both inside the first (only) segment

    result = strip_meeting_path_from_pillars(curve, pillars, meetings, current_policy_rate=0.10)
    assert len(result) == 2
    for r in result:
        assert r.implied_change_bps == pytest.approx(0.0, abs=1e-6)


def test_strip_from_pillars_splits_65_35_across_two_meetings_in_one_segment():
    valuation_date = date(2026, 1, 5)
    pillar_1, pillar_2 = date(2026, 6, 1), date(2027, 6, 1)
    curve = _curve_from_rates(valuation_date, {pillar_1: 0.10, pillar_2: 0.11})
    # both meetings fall inside the (pillar_1, pillar_2] segment -- only one
    # real number (the segment's own implied change) describes both of them
    meetings = [date(2026, 8, 1), date(2026, 11, 1)]

    result = strip_meeting_path_from_pillars(curve, [pillar_1, pillar_2], meetings, current_policy_rate=0.10)
    assert len(result) == 2
    total = result[0].implied_change_bps + result[1].implied_change_bps
    assert result[0].implied_change_bps == pytest.approx(total * 0.65, rel=1e-6)
    assert result[1].implied_change_bps == pytest.approx(total * 0.35, rel=1e-6)
    assert result[0].implied_change_bps > result[1].implied_change_bps > 0  # front-loaded


def test_strip_from_pillars_three_meetings_first_gets_65_rest_split_evenly():
    valuation_date = date(2026, 1, 5)
    pillar_1, pillar_2 = date(2026, 6, 1), date(2027, 6, 1)
    curve = _curve_from_rates(valuation_date, {pillar_1: 0.10, pillar_2: 0.11})
    meetings = [date(2026, 7, 1), date(2026, 9, 1), date(2026, 11, 1)]

    result = strip_meeting_path_from_pillars(curve, [pillar_1, pillar_2], meetings, current_policy_rate=0.10)
    assert len(result) == 3
    total = sum(r.implied_change_bps for r in result)
    assert result[0].implied_change_bps == pytest.approx(total * 0.65, rel=1e-6)
    assert result[1].implied_change_bps == pytest.approx(result[2].implied_change_bps, rel=1e-6)


def test_strip_from_pillars_single_meeting_per_segment_gets_full_change():
    valuation_date = date(2026, 1, 5)
    pillar_1, pillar_2 = date(2026, 6, 1), date(2027, 6, 1)
    curve = _curve_from_rates(valuation_date, {pillar_1: 0.10, pillar_2: 0.11})
    meetings = [date(2026, 3, 1)]  # exactly one meeting, inside the first segment

    result = strip_meeting_path_from_pillars(curve, [pillar_1, pillar_2], meetings, current_policy_rate=0.10)
    assert len(result) == 1
    expected = (curve.forward_rate(valuation_date, pillar_1) - 0.10) * 1e4
    assert result[0].implied_change_bps == pytest.approx(expected, abs=1e-6)


def test_strip_from_pillars_empty_segment_carries_change_to_next_meeting():
    valuation_date = date(2026, 1, 5)
    pillar_1, pillar_2, pillar_3 = date(2026, 6, 1), date(2026, 9, 1), date(2027, 6, 1)
    curve = _curve_from_rates(valuation_date, {pillar_1: 0.10, pillar_2: 0.11, pillar_3: 0.11})
    # meeting falls in the 3rd segment (after pillar_2) -- neither of the two
    # earlier segments (valuation->pillar_1, pillar_1->pillar_2) has a
    # meeting of its own, so their changes must telescope forward rather
    # than vanish: the meeting should see the FULL move from the original
    # policy_rate baseline to this segment's own level, not just this
    # segment's isolated slice of it.
    meetings = [date(2026, 10, 1)]

    result = strip_meeting_path_from_pillars(curve, [pillar_1, pillar_2, pillar_3], meetings, current_policy_rate=0.10)
    assert len(result) == 1
    # pillar_2 and pillar_3 share the same rate, so the curve's own forward
    # over that segment is exactly that rate -- a clean, hand-checkable case.
    expected = (0.11 - 0.10) * 1e4
    assert result[0].implied_change_bps == pytest.approx(expected, abs=1e-6)
