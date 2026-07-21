from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.scenarios.comparison import (
    hikes_cuts_by_year_table,
    meeting_comparison_table,
    vertex_comparison_table,
)
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.model import Scenario, Shock

VALUATION_DATE = date(2026, 1, 5)
MEETINGS = [
    date(2026, 3, 1),
    date(2026, 4, 15),
    date(2026, 6, 1),
    date(2027, 1, 15),  # crosses into a new year
    date(2027, 3, 1),
]


def _curve() -> DiscountCurve:
    pillar_rates = {d: 0.10 for d in MEETINGS}
    pillar_dates = sorted(pillar_rates)
    dfs = [(1 + pillar_rates[d]) ** (-((d - VALUATION_DATE).days / 365)) for d in pillar_dates]
    return DiscountCurve(VALUATION_DATE, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_meeting_comparison_table_has_one_column_per_scenario():
    curve = _curve()
    scenario_a = Scenario(name="A", country="brazil", shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=-50.0)])
    scenario_b = Scenario(name="B", country="brazil", shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=20.0)])
    curves = {
        "A": build_scenario_curve(curve, MEETINGS, scenario_a),
        "B": build_scenario_curve(curve, MEETINGS, scenario_b),
    }
    df = meeting_comparison_table(curve, curves, MEETINGS, current_policy_rate=0.10)
    assert list(df.columns) == ["meeting_date", "mkt", "A", "B"]
    assert list(df["mkt"]) == pytest.approx([0.0, 0.0, 0.0, 0.0], abs=1e-6)
    row_for_meeting1 = df[df["meeting_date"] == MEETINGS[1]].iloc[0]
    assert row_for_meeting1["A"] == pytest.approx(-50.0, abs=1e-6)
    assert row_for_meeting1["B"] == pytest.approx(20.0, abs=1e-6)


def test_hikes_cuts_by_year_sums_within_each_calendar_year():
    curve = _curve()
    scenario = Scenario(name="A", country="brazil", shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=-50.0)])
    curves = {"A": build_scenario_curve(curve, MEETINGS, scenario)}
    meeting_df = meeting_comparison_table(curve, curves, MEETINGS, current_policy_rate=0.10)

    by_year = hikes_cuts_by_year_table(meeting_df)
    assert list(by_year["year"]) == [2026, 2027]
    # 2026 meetings are meeting_dates[0..2] (the 2027 ones dropped by strip_meeting_path's horizon rule)
    assert by_year[by_year["year"] == 2026]["A"].iloc[0] == pytest.approx(-50.0, abs=1e-6)


def test_vertex_comparison_table_has_rate_and_delta_columns_per_scenario():
    curve = _curve()
    scenario = Scenario(name="A", country="brazil", shocks=[Shock(meeting_date=MEETINGS[0], shock_bps=25.0)])
    curves = {"A": build_scenario_curve(curve, MEETINGS, scenario)}
    df = vertex_comparison_table(curve, curves)
    assert list(df.columns) == ["maturity", "mkt_pct", "A_pct", "A_delta_bps"]
    assert list(df["maturity"]) == curve.pillar_dates
