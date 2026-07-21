"""Compares several named scenarios side by side for one country — same
shape as a trader's own scenario spreadsheet: meetings (and years, and
curve vertices) as rows, market + each scenario as columns, so a whole set
of "what if" views can be read at a glance instead of one HTML per
scenario.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from emrates.central_banks.stripper import strip_meeting_path
from emrates.curves.base import DiscountCurve
from emrates.scenarios.curve import ScenarioCurve


def meeting_comparison_table(
    base_curve: DiscountCurve,
    scenario_curves: dict[str, ScenarioCurve],
    meeting_dates: list[date],
    current_policy_rate: float,
) -> pd.DataFrame:
    """One row per meeting; 'mkt' + one column per scenario, each the bps change priced AT that meeting."""
    base = strip_meeting_path(base_curve, meeting_dates, current_policy_rate)
    rows = [{"meeting_date": r.meeting_date, "mkt": round(r.implied_change_bps, 1)} for r in base]
    for name, curve in scenario_curves.items():
        scenario_results = strip_meeting_path(curve, meeting_dates, current_policy_rate)
        for row, r in zip(rows, scenario_results):
            row[name] = round(r.implied_change_bps, 1)
    return pd.DataFrame(rows)


def hikes_cuts_by_year_table(meeting_table: pd.DataFrame) -> pd.DataFrame:
    """Sums meeting_comparison_table's per-meeting columns by calendar year."""
    by_year = meeting_table.drop(columns=["meeting_date"]).copy()
    by_year["year"] = [d.year for d in meeting_table["meeting_date"]]
    return by_year.groupby("year", as_index=False).sum().round(1)


def vertex_comparison_table(
    base_curve: DiscountCurve,
    scenario_curves: dict[str, ScenarioCurve],
) -> pd.DataFrame:
    """One row per curve vertex (market pillar); mkt rate, then each scenario's
    rate and its delta vs mkt, in bps."""
    rows = [{"maturity": m, "mkt_pct": round(base_curve.zero_rate(m) * 100, 3)} for m in base_curve.pillar_dates]
    for name, curve in scenario_curves.items():
        for row, m in zip(rows, base_curve.pillar_dates):
            scenario_rate = curve.zero_rate(m)
            row[f"{name}_pct"] = round(scenario_rate * 100, 3)
            row[f"{name}_delta_bps"] = round((scenario_rate - base_curve.zero_rate(m)) * 1e4, 1)
    return pd.DataFrame(rows)
