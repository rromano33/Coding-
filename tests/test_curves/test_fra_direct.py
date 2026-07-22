from datetime import date, timedelta

import pytest

from emrates.curves.fra_direct import fra_priced_path

SPOT = date(2026, 7, 22)


def _date_at_months(months: float) -> date:
    return SPOT + timedelta(days=months * 30.4368)


def test_reproduces_the_real_czech_reference_table_bps_for_bps():
    # Real numbers from the desk's own FRA reference sheet (Czech, Ref Rate
    # 3.85): outright rate per FRA end-month, and the cumulative bps they
    # compute by hand (outright - ref_rate). If BC meetings happened to
    # fall exactly on FRA end-months, our cumulative must match theirs.
    ref_rate = 0.0385
    outright_pct = {4: 3.97, 5: 4.05, 6: 4.11, 7: 4.21, 8: 4.32, 9: 4.39, 10: 4.43, 11: 4.47, 12: 4.49}
    fra_data = [(m - 3, m, r / 100.0) for m, r in outright_pct.items()]  # (start,end,rate) tuples like real tickers

    meeting_dates = [_date_at_months(m) for m in sorted(outright_pct)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meeting_dates)

    their_cumulative_bps = {4: 11.8, 5: 19.8, 6: 25.8, 7: 35.8, 8: 47.0, 9: 54.3, 10: 58.0, 11: 62.0, 12: 64.0}
    for r, month in zip(results, sorted(outright_pct)):
        assert r.cumulative_change_from_spot_bps == pytest.approx(their_cumulative_bps[month], abs=1.0)


def test_uses_every_overlapping_fra_quote_not_just_a_chain():
    # Unlike fra_strip's best_chain_start (which must pick ONE non-overlapping
    # chain), every quote in a rolling monthly strip should feed the
    # interpolation directly, overlaps and all.
    ref_rate = 0.05
    fra_data = [(1, 4, 0.048), (2, 5, 0.047), (3, 6, 0.046), (4, 7, 0.045)]
    meetings = [_date_at_months(m) for m in [4, 5, 6, 7]]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings)
    assert len(results) == 4
    assert [round(r.level_after_bps) for r in results] == [round(v * 1e4) for v in (0.048, 0.047, 0.046, 0.045)]


def test_meeting_between_fra_points_gets_linearly_interpolated():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.05), (4, 7, 0.06)]  # flat then a step up
    meeting_at_5_5_months = _date_at_months(5.5)  # halfway between month 4 and month 7
    meetings = [_date_at_months(4), meeting_at_5_5_months, _date_at_months(7)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings)
    midpoint_level = results[1].level_after_bps / 1e4
    assert midpoint_level == pytest.approx(0.055, abs=1e-4)  # halfway between 0.05 and 0.06


def test_beyond_last_fra_point_holds_flat():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.048)]
    meetings = [_date_at_months(4), _date_at_months(20), _date_at_months(24)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings)
    assert results[-1].implied_change_bps == pytest.approx(0.0, abs=1e-6)  # flat past month 4


def test_first_meeting_change_is_measured_from_ref_rate():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.0525)]
    meetings = [_date_at_months(4)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings)
    assert results[0].implied_change_bps == pytest.approx(25.0, abs=0.5)
    assert results[0].cumulative_change_from_spot_bps == pytest.approx(25.0, abs=0.5)
