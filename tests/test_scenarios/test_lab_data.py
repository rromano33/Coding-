from datetime import date

import pytest

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.scenarios.lab_data import build_lab_skeleton

VALUATION_DATE = date(2026, 1, 5)
MEETINGS = [date(2026, 3, 1), date(2026, 4, 15), date(2026, 6, 1)]


def _curve(pillar_dates, rate=0.10) -> DiscountCurve:
    pillar_dates = sorted(set(pillar_dates))
    dfs = [(1 + rate) ** (-((d - VALUATION_DATE).days / 365)) for d in pillar_dates]
    return DiscountCurve(VALUATION_DATE, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)


def test_skeleton_has_one_meeting_entry_per_meeting_with_correct_tau_and_forward():
    curve = _curve(MEETINGS)
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)

    assert [m["date"] for m in skeleton["meetings"]] == [d.isoformat() for d in MEETINGS]
    assert skeleton["meetings"][0]["tau"] == pytest.approx(curve.tau(VALUATION_DATE, MEETINGS[0]))
    assert skeleton["meetings"][1]["tau"] == pytest.approx(curve.tau(MEETINGS[0], MEETINGS[1]))
    assert skeleton["meetings"][0]["market_forward_pct"] == pytest.approx(
        curve.forward_rate(VALUATION_DATE, MEETINGS[0]) * 100
    )


def test_meeting_market_change_bps_is_delta_vs_previous_segment_not_cumulative():
    curve = _curve(MEETINGS, rate=0.10)  # curva flat -- toda mudança vem só da taxa de política inicial
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)

    # 1a reunião: mercado (flat 10%) vs taxa de política atual (9.5%) -> +50bps
    assert skeleton["meetings"][0]["market_change_bps"] == pytest.approx(50.0, abs=1e-6)
    # reuniões seguintes: curva flat -> forward igual ao segmento anterior -> 0bps
    assert skeleton["meetings"][1]["market_change_bps"] == pytest.approx(0.0, abs=1e-6)
    assert skeleton["meetings"][2]["market_change_bps"] == pytest.approx(0.0, abs=1e-6)


def test_skeleton_top_level_fields():
    curve = _curve(MEETINGS)
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)
    assert skeleton["valuation_date"] == VALUATION_DATE.isoformat()
    assert skeleton["compounding"] == "exponential"
    assert skeleton["current_policy_rate_pct"] == pytest.approx(9.5)


def test_vertex_within_horizon_gets_segment_index_and_local_tau():
    # vértice cai dentro do 2º segmento (entre a 1ª e a 2ª reunião)
    vertex_date = date(2026, 4, 1)
    curve = _curve([vertex_date] + MEETINGS)
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)

    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["segment_index"] == 2  # boundary_dates = [val, m0, m1, m2] -- m1 é o índice 2
    assert entry["tau_from_segment_start"] == pytest.approx(curve.tau(MEETINGS[0], vertex_date))
    assert "tail_tau" not in entry


def test_vertex_beyond_last_meeting_gets_tail_fields():
    vertex_date = date(2027, 1, 1)  # depois da última reunião (2026-06-01)
    curve = _curve([vertex_date] + MEETINGS)
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)

    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["segment_index"] is None
    assert entry["tail_tau"] == pytest.approx(curve.tau(MEETINGS[-1], vertex_date))
    assert entry["tail_base_forward_pct"] == pytest.approx(curve.forward_rate(MEETINGS[-1], vertex_date) * 100)


def test_vertex_market_zero_matches_curve_directly():
    vertex_date = MEETINGS[1]
    curve = _curve([vertex_date] + MEETINGS, rate=0.12)
    skeleton = build_lab_skeleton(curve, MEETINGS, current_policy_rate=0.095)
    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["market_zero_pct"] == pytest.approx(curve.zero_rate(vertex_date) * 100)


def test_raises_when_no_meetings_given():
    curve = _curve(MEETINGS)
    with pytest.raises(ValueError, match="pelo menos 1 reunião"):
        build_lab_skeleton(curve, [], current_policy_rate=0.095)
