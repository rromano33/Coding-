"""Turns a ScenarioCurve into (1) the same meeting-path shape as
reports/priced_bc.py, compared against the base curve, and (2) a per-vertex
(the curve's own market pillars — DI1 contracts for Brazil) rate impact
table, so a trade idea can be sized against a specific tradeable contract.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from emrates.central_banks.stripper import strip_meeting_path
from emrates.curves.base import DiscountCurve
from emrates.scenarios.curve import ScenarioCurve


def scenario_meeting_report(
    base_curve: DiscountCurve,
    scenario_curve: ScenarioCurve,
    meeting_dates: list[date],
    current_policy_rate: float,
) -> pd.DataFrame:
    base = strip_meeting_path(base_curve, meeting_dates, current_policy_rate)
    scenario = strip_meeting_path(scenario_curve, meeting_dates, current_policy_rate)
    rows = [
        {
            "meeting_date": b.meeting_date,
            "base_implied_change_bps": round(b.implied_change_bps, 1),
            "scenario_implied_change_bps": round(s.implied_change_bps, 1),
            "base_cumulative_bps": round(b.cumulative_change_from_spot_bps, 1),
            "scenario_cumulative_bps": round(s.cumulative_change_from_spot_bps, 1),
            "delta_vs_base_bps": round(s.cumulative_change_from_spot_bps - b.cumulative_change_from_spot_bps, 1),
        }
        for b, s in zip(base, scenario)
    ]
    return pd.DataFrame(rows)


def vertex_impact_report(base_curve: DiscountCurve, scenario_curve: ScenarioCurve) -> pd.DataFrame:
    rows = [
        {
            "maturity": maturity,
            "base_rate_pct": round(base_curve.zero_rate(maturity) * 100, 3),
            "scenario_rate_pct": round(scenario_curve.zero_rate(maturity) * 100, 3),
            "delta_bps": round((scenario_curve.zero_rate(maturity) - base_curve.zero_rate(maturity)) * 1e4, 1),
        }
        for maturity in base_curve.pillar_dates
    ]
    return pd.DataFrame(rows)
