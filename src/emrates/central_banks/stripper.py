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
