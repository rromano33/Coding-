"""Direct FRA-quote pricing path for Czech/Poland/Hungary — treats each
FRA's own quoted outright rate as a direct market observation of the
forward curve at that end-month, and gets "what's priced by meeting X" via
linear interpolation. No bootstrap, no discount factors, no curve-smoothing.

This exists alongside curves/fra_strip.py (which splices FRA quotes into a
full discount curve — needed for POSITION valuation/PnL, where a
continuous curve is required) as a simpler, more direct alternative
specifically for the priced_bc report. Chaining FRA quotes into a discount
curve and then smoothing with NSS (curves/nss.py) compounds two sources of
amplification — a seam where the FRA-implied path meets the swap-curve-
implied path, plus NSS's own tendency to overshoot around that seam — that
reading the FRA quotes directly sidesteps entirely (confirmed: it produced
~2x the priced move a direct read implies, and a wrong sign for Hungary
when 2 of its FRA quotes came back NaN and broke the bootstrap chain).

It also uses every FRA quote available — a rolling monthly strip like
1X4, 2X5, 3X6, ..., 9X12 has far more points than any single non-
overlapping bootstrap chain can use — and matches, by construction, the
plain "outright rate minus reference rate" arithmetic the desk's own
manual reference sheet already uses (verified bps-for-bps against it).
"""
from __future__ import annotations

from datetime import date

from emrates.central_banks.stripper import MeetingPricing
from emrates.curves.fra_strip import month_offset
from emrates.data.calendars import Calendar


def fra_priced_path(
    spot_date: date,
    ref_rate: float,
    fra_data: list[tuple[int, int, float]],
    meeting_dates: list[date],
    calendar: Calendar,
) -> list[MeetingPricing]:
    """fra_data: (start_month, end_month, rate) as parsed from FRA tickers —
    every quote is used as an (end_month, rate) point, overlaps and all.

    Interpolates over real calendar day-counts from spot, not a nominal
    "N months = N*30.4368 days" approximation: a FRA's end_month label is a
    *calendar*-month offset (see fra_strip.month_offset — same day-of-month,
    N months later, business-day adjusted), which doesn't sit at a uniform
    30.4368-day cadence in general (real months run 28-31 days). Using the
    bare integer label as the x-axis for FRA points while converting meeting
    dates through a fixed average-month divisor mismatches the two axes'
    units and biases the interpolated level — small per point, but it
    compounds across several months (this was the residual gap after the
    first fix: Czech matched the reference closely, Poland still ran
    noticeably low). Computing each FRA point's actual date the same way
    fra_strip.py does, and comparing real day-counts throughout, removes
    that bias.

    Unlike central_banks.stripper.strip_meeting_path (which treats meeting
    dates as *boundaries* between inter-meeting forward-rate segments, and
    needs one extra meeting past the horizon to read the last one's 'after'
    level), this treats each meeting date as its own *point* on the FRA-
    implied level curve — matching the reference sheet's own row-by-row
    arithmetic exactly: cumulative at meeting i = level at meeting i's own
    date minus ref_rate; the change priced at meeting i is that level minus
    the previous meeting's (or ref_rate, for the first meeting). No extra
    trailing meeting needed — every date passed in gets its own row."""
    points = sorted({(end, rate) for _, end, rate in fra_data})
    xs = [0] + [(calendar.adjust_following(month_offset(spot_date, end)) - spot_date).days for end, _ in points]
    ys = [ref_rate] + [rate for _, rate in points]

    def level_at(days_from_spot: int) -> float:
        if days_from_spot <= xs[0]:
            return ys[0]
        if days_from_spot >= xs[-1]:
            return ys[-1]
        for i in range(1, len(xs)):
            if days_from_spot <= xs[i]:
                t = (days_from_spot - xs[i - 1]) / (xs[i] - xs[i - 1])
                return ys[i - 1] + t * (ys[i] - ys[i - 1])
        return ys[-1]

    meeting_dates = sorted(meeting_dates)
    results = []
    prev_level = ref_rate
    cumulative = 0.0
    for meeting_date in meeting_dates:
        level = level_at((meeting_date - spot_date).days)
        change_bps = (level - prev_level) * 1e4
        cumulative += change_bps
        results.append(
            MeetingPricing(
                meeting_date=meeting_date,
                level_before_bps=prev_level * 1e4,
                level_after_bps=level * 1e4,
                implied_change_bps=change_bps,
                cumulative_change_from_spot_bps=cumulative,
            )
        )
        prev_level = level
    return results
