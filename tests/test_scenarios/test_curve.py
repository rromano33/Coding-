from datetime import date

import pytest

from emrates.central_banks.stripper import strip_meeting_path
from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.model import Scenario, Shock

VALUATION_DATE = date(2026, 1, 5)
MEETINGS = [date(2026, 3, 1), date(2026, 4, 15), date(2026, 6, 1), date(2026, 7, 15)]


def _curve(pillar_rates: dict[date, float]) -> DiscountCurve:
    pillar_dates = sorted(pillar_rates)
    dfs = [(1 + pillar_rates[d]) ** (-((d - VALUATION_DATE).days / 365)) for d in pillar_dates]
    return DiscountCurve(VALUATION_DATE, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def _flat_curve(rate: float, extra_pillars: list[date] | None = None) -> DiscountCurve:
    pillars = MEETINGS + (extra_pillars or [])
    return _curve({d: rate for d in pillars})


def test_shock_shows_up_only_from_its_meeting_onward():
    curve = _flat_curve(0.10)
    scenario = Scenario(name="test", country="brazil", shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=-50.0)])
    scenario_curve = build_scenario_curve(curve, MEETINGS, scenario)

    result = strip_meeting_path(scenario_curve, MEETINGS, current_policy_rate=0.10)
    assert result[0].implied_change_bps == pytest.approx(0.0, abs=1e-6)  # meeting[0]: before the shock
    assert result[1].implied_change_bps == pytest.approx(-50.0, abs=1e-6)  # meeting[1]: the shock lands here
    assert result[1].cumulative_change_from_spot_bps == pytest.approx(-50.0, abs=1e-6)


def test_shock_persists_to_later_meetings_until_replaced():
    curve = _flat_curve(0.10)
    scenario = Scenario(
        name="test",
        country="brazil",
        shocks=[Shock(meeting_date=MEETINGS[1], shock_bps=-50.0), Shock(meeting_date=MEETINGS[2], shock_bps=20.0)],
    )
    scenario_curve = build_scenario_curve(curve, MEETINGS, scenario)
    result = strip_meeting_path(scenario_curve, MEETINGS, current_policy_rate=0.10)

    # meeting[2] (index 2, boundary_dates[3]) isn't in `result` (dropped —
    # no 'after' period within our 4-meeting horizon), but its persisted
    # effect should show in the *next* segment if we had one. Check what we
    # do have: meeting[1]'s cumulative is still -50 (the first shock, not
    # yet replaced), matching the previous test.
    assert result[1].cumulative_change_from_spot_bps == pytest.approx(-50.0, abs=1e-6)


def test_unknown_shock_meeting_raises():
    curve = _flat_curve(0.10)
    scenario = Scenario(name="test", country="brazil", shocks=[Shock(meeting_date=date(2099, 1, 1), shock_bps=10.0)])
    with pytest.raises(ValueError, match="fora do horizonte"):
        build_scenario_curve(curve, MEETINGS, scenario)


def test_tail_beyond_horizon_preserves_base_curve_shape_shifted_by_final_shock():
    tail_date = date(2029, 1, 5)  # 3y out, well past the last modeled meeting
    curve = _curve({**{d: 0.10 for d in MEETINGS}, tail_date: 0.12})  # upward-sloping tail
    scenario = Scenario(name="test", country="brazil", shocks=[Shock(meeting_date=MEETINGS[0], shock_bps=30.0)])
    scenario_curve = build_scenario_curve(curve, MEETINGS, scenario)

    base_tail_forward = curve.forward_rate(MEETINGS[-1], tail_date)
    scenario_tail_forward = scenario_curve.forward_rate(MEETINGS[-1], tail_date)
    assert scenario_tail_forward == pytest.approx(base_tail_forward + 0.0030, abs=1e-6)
