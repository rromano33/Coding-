from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.model import Scenario, Shock
from emrates.scenarios.report import scenario_meeting_report, vertex_impact_report

VALUATION_DATE = date(2026, 1, 5)
MEETINGS = [date(2026, 3, 1), date(2026, 4, 15), date(2026, 6, 1), date(2026, 7, 15)]
TAIL_DATE = date(2029, 1, 5)


def _curve() -> DiscountCurve:
    pillar_rates = {**{d: 0.10 for d in MEETINGS}, TAIL_DATE: 0.12}
    pillar_dates = sorted(pillar_rates)
    dfs = [(1 + pillar_rates[d]) ** (-((d - VALUATION_DATE).days / 365)) for d in pillar_dates]
    return DiscountCurve(VALUATION_DATE, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_scenario_meeting_report_shows_delta_vs_base():
    curve = _curve()
    scenario = Scenario(name="test", country="brazil", shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=-50.0)])
    scenario_curve = build_scenario_curve(curve, MEETINGS, scenario)

    df = scenario_meeting_report(curve, scenario_curve, MEETINGS, current_policy_rate=0.10)
    assert list(df["delta_vs_base_bps"]) == pytest.approx([0.0, -50.0, -50.0], abs=1e-6)


def test_vertex_impact_report_matches_curve_pillars():
    curve = _curve()
    scenario = Scenario(name="test", country="brazil", shocks=[Shock(meeting_date=MEETINGS[0], shock_bps=30.0)])
    scenario_curve = build_scenario_curve(curve, MEETINGS, scenario)

    df = vertex_impact_report(curve, scenario_curve)
    assert list(df["maturity"]) == curve.pillar_dates
    for _, row in df.iterrows():
        expected_delta = (scenario_curve.zero_rate(row["maturity"]) - curve.zero_rate(row["maturity"])) * 1e4
        assert row["delta_bps"] == pytest.approx(round(expected_delta, 1), abs=1e-6)
    # the shock lands *after* MEETINGS[0], so the pillar at MEETINGS[0] itself
    # (entirely within the unshocked stub) shouldn't move, while the tail
    # (well past the shock) should be close to the full +30bps.
    first_row = df[df["maturity"] == MEETINGS[0]].iloc[0]
    tail_row = df[df["maturity"] == TAIL_DATE].iloc[0]
    assert first_row["delta_bps"] == pytest.approx(0.0, abs=1e-6)
    assert tail_row["delta_bps"] == pytest.approx(28.5, abs=0.1)
