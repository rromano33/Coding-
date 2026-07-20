"""Builds the 'what's priced for each Central Bank' report for one country."""
from __future__ import annotations

from datetime import date

import pandas as pd

from emrates.central_banks.stripper import strip_meeting_path
from emrates.curves.base import DiscountCurve


def priced_bc_report(curve: DiscountCurve, meeting_dates: list[date], current_policy_rate: float) -> pd.DataFrame:
    results = strip_meeting_path(curve, meeting_dates, current_policy_rate)
    return pd.DataFrame(
        [
            {
                "meeting_date": r.meeting_date,
                "level_before_bps": round(r.level_before_bps, 1),
                "level_after_bps": round(r.level_after_bps, 1),
                "implied_change_bps": round(r.implied_change_bps, 1),
                "cumulative_change_from_spot_bps": round(r.cumulative_change_from_spot_bps, 1),
            }
            for r in results
        ]
    )
