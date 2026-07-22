from datetime import date, timedelta

import pytest

from emrates.curves.fra_direct import fra_priced_path
from emrates.curves.fra_strip import month_offset
from emrates.data.calendars import Calendar

SPOT = date(2026, 7, 22)
CALENDAR = Calendar("test", holidays=set())


def _date_at_months(months: float) -> date:
    # Exact calendar-month arithmetic for whole months (matches how the code
    # itself positions FRA points); falls back to the day-based approximation
    # only for the fractional-month case (a meeting strictly between two FRA
    # end-months), where there's no "exact" answer to match anyway.
    if months == int(months):
        return CALENDAR.adjust_modified_following(month_offset(SPOT, int(months)))
    return SPOT + timedelta(days=months * 30.4368)


def test_reproduces_the_real_czech_reference_table_bps_for_bps():
    # Real numbers from the desk's own FRA reference sheet (Czech, Ref Rate
    # 3.85): outright rate per FRA end-month, and the cumulative bps they
    # compute by hand (outright - ref_rate). If BC meetings happened to
    # fall exactly on FRA end-months, our cumulative must match theirs.
    ref_rate = 0.0385
    outright_pct = {4: 3.97, 5: 4.05, 6: 4.11, 7: 4.21, 8: 4.32, 9: 4.39, 10: 4.43, 11: 4.47, 12: 4.49}
    fra_data = [(m - 3, m, r / 100.0) for m, r in outright_pct.items()]  # (start,end,rate) tuples like real tickers

    meeting_dates = [CALENDAR.adjust_modified_following(month_offset(SPOT, m)) for m in sorted(outright_pct)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meeting_dates, CALENDAR)

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
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings, CALENDAR)
    assert len(results) == 4
    assert [round(r.level_after_bps) for r in results] == [round(v * 1e4) for v in (0.048, 0.047, 0.046, 0.045)]


def test_meeting_between_fra_points_gets_linearly_interpolated():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.05), (4, 7, 0.06)]  # flat then a step up
    meeting_at_5_5_months = _date_at_months(5.5)  # roughly halfway between month 4 and month 7
    meetings = [_date_at_months(4), meeting_at_5_5_months, _date_at_months(7)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings, CALENDAR)
    midpoint_level = results[1].level_after_bps / 1e4
    assert midpoint_level == pytest.approx(0.055, abs=2e-3)  # roughly halfway between 0.05 and 0.06


def test_beyond_last_fra_point_holds_flat():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.048)]
    meetings = [_date_at_months(4), _date_at_months(20), _date_at_months(24)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings, CALENDAR)
    assert results[-1].implied_change_bps == pytest.approx(0.0, abs=1e-6)  # flat past month 4


def test_first_meeting_change_is_measured_from_ref_rate():
    ref_rate = 0.05
    fra_data = [(1, 4, 0.0525)]
    meetings = [_date_at_months(4)]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings, CALENDAR)
    assert results[0].implied_change_bps == pytest.approx(25.0, abs=0.5)
    assert results[0].cumulative_change_from_spot_bps == pytest.approx(25.0, abs=0.5)


def test_short_term_meetings_read_close_to_the_first_fra_not_smeared_toward_it():
    # Real Hungary numbers: Ref Rate 5.60, first FRA quote is "1X4" (starts 1
    # month out, ends 4 months out) at 5.49% (-11.0bps). Before this fix, a
    # meeting 1-2 months out (well inside the FRA's own window) read only
    # -3 to -5.5bps — a straight line from ref_rate smeared "1X4"'s move
    # evenly across the whole 4-month gap, when the quote itself says the
    # market expects close to -11bps for the ENTIRE window starting at
    # month 1. A meeting near month 1 should already read close to -11bps.
    ref_rate = 0.0560
    fra_data = [(1, 4, 0.0549), (4, 7, 0.0536), (7, 10, 0.0526)]
    meetings = [_date_at_months(m) for m in [1, 2, 3, 4]]
    results = fra_priced_path(SPOT, ref_rate, fra_data, meetings, CALENDAR)
    for r in results:
        assert r.cumulative_change_from_spot_bps == pytest.approx(-11.0, abs=1.0)


def test_fra_point_positioned_at_its_real_calendar_date_not_a_month_average():
    # A FRA end-month is calendar-month arithmetic (same day-of-month, N
    # months later — see fra_strip.month_offset), not a fixed 30.4368-day
    # step. Positioning it correctly matters: a meeting landing exactly on
    # the FRA's own real calendar date must read that FRA's exact rate, even
    # though a 30.4368*N-day approximation would place it a few days off.
    ref_rate = 0.05
    fra_data = [(1, 9, 0.06)]  # a FRA ending 9 calendar-months from spot
    real_end_date = CALENDAR.adjust_modified_following(month_offset(SPOT, 9))
    results = fra_priced_path(SPOT, ref_rate, fra_data, [real_end_date], CALENDAR)
    assert results[0].level_after_bps == pytest.approx(0.06 * 1e4, abs=1e-6)
