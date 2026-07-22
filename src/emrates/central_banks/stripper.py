"""Meeting-dated stripping: turns a discount curve into 'how many bps of
hike/cut does the market have priced at each Central Bank meeting'.

Method: build [valuation_date, meeting_1, meeting_2, ...] as pillar dates,
take the curve's forward rate over each consecutive interval (piecewise-
constant, one level per inter-meeting period), and read the jump between
consecutive levels as the change priced for the meeting that starts that
period. This is the standard meeting-dated OIS stripping technique rates
desks use to quote 'X bps priced' for the next N decisions.

Note: the change priced AT meeting[i] is read from the period that starts
at meeting[i], i.e. levels[i+1]. Pass at least one meeting date beyond the
last one you actually care about — otherwise that last meeting has no
'after' period to read a priced change from, and is dropped from the result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from emrates.central_banks.segment_split import split_segment_change
from emrates.curves.base import DiscountCurve


@dataclass
class MeetingPricing:
    meeting_date: date
    level_before_bps: float
    level_after_bps: float
    implied_change_bps: float
    cumulative_change_from_spot_bps: float


def strip_meeting_path(
    curve: DiscountCurve,
    meeting_dates: list[date],
    current_policy_rate: float,
) -> list[MeetingPricing]:
    if len(meeting_dates) < 2:
        return []
    meeting_dates = sorted(meeting_dates)
    boundary_dates = [curve.valuation_date] + meeting_dates
    levels = [
        curve.forward_rate(boundary_dates[i], boundary_dates[i + 1]) for i in range(len(boundary_dates) - 1)
    ]
    # levels[0]: pre-first-meeting stub (sanity check vs current_policy_rate)
    # levels[i], i>=1: rate prevailing after meeting_dates[i-1]'s decision

    results = []
    cumulative = 0.0
    for i in range(len(meeting_dates) - 1):
        before = levels[i]
        after = levels[i + 1]
        change_bps = (after - before) * 1e4
        cumulative += change_bps
        results.append(
            MeetingPricing(
                meeting_date=meeting_dates[i],
                level_before_bps=before * 1e4,
                level_after_bps=after * 1e4,
                implied_change_bps=change_bps,
                cumulative_change_from_spot_bps=cumulative,
            )
        )
    return results


def strip_meeting_path_from_pillars(
    curve: DiscountCurve,
    pillar_dates: list[date],
    meeting_dates: list[date],
    current_policy_rate: float,
    first_weight: float = 0.65,
) -> list[MeetingPricing]:
    """For countries with no FRA strip (e.g. Colombia), where the swap
    curve's own real pillars are sparser than the BC's meeting calendar —
    reads each segment's implied change straight off ADJACENT REAL PILLARS
    (curve.forward_rate between two actual market dates, never an
    interpolated point in between), then splits that one number across
    however many real meetings fall inside the segment (see
    segment_split.split_segment_change) instead of running it through NSS.

    NSS fits one smooth 6-parameter curve across every pillar, short and
    sparse-long alike — asking it to also resolve meeting-level detail past
    what a handful of sparse pillars can support tends to overshoot instead
    of smoothing (confirmed: it diverged worse than the exact curve against
    a reference path for Colombia). Reading real pillars directly and
    declaring the split explicitly is more honest about the fact that the
    market data itself doesn't distinguish which meeting in a multi-meeting
    segment actually moves the rate.

    pillar_dates: the curve's own real market pillars (e.g. curve.pillar_dates
    with any illiquid ones already filtered out by the caller).
    meeting_dates: every real BC meeting within the horizon you care about —
    unlike strip_meeting_path, no trailing extra meeting is needed (each
    pillar segment's change is fully attributed to the meetings inside it)."""
    pillar_dates = sorted(pillar_dates)
    meeting_dates = sorted(meeting_dates)
    boundary_dates = [curve.valuation_date] + pillar_dates
    levels = [
        curve.forward_rate(boundary_dates[i], boundary_dates[i + 1]) for i in range(len(boundary_dates) - 1)
    ]

    results: list[MeetingPricing] = []
    # prev_level: the most recent segment's own level, advances every
    # iteration regardless of whether that segment had a meeting — a gap
    # with no meeting must not leave later segments comparing against a
    # stale, several-segments-old reference.
    prev_level = current_policy_rate
    # running_level: the level actually realized via attributed meetings so
    # far — only this one feeds level_before/level_after bookkeeping.
    running_level = current_policy_rate
    pending_change_bps = 0.0
    cumulative = 0.0
    for i in range(len(levels)):
        seg_start, seg_end = boundary_dates[i], boundary_dates[i + 1]
        change_bps = (levels[i] - prev_level) * 1e4 + pending_change_bps
        prev_level = levels[i]
        segment_meetings = [m for m in meeting_dates if seg_start < m <= seg_end]
        if not segment_meetings:
            pending_change_bps = change_bps
            continue
        pending_change_bps = 0.0
        for meeting_date, delta_bps in zip(segment_meetings, split_segment_change(change_bps, len(segment_meetings), first_weight)):
            before_bps = running_level * 1e4
            running_level += delta_bps / 1e4
            cumulative += delta_bps
            results.append(
                MeetingPricing(
                    meeting_date=meeting_date,
                    level_before_bps=before_bps,
                    level_after_bps=running_level * 1e4,
                    implied_change_bps=delta_bps,
                    cumulative_change_from_spot_bps=cumulative,
                )
            )
    return results
