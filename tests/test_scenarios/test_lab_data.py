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


def _reports(meetings=MEETINGS, implied_change_bps=None):
    """meeting_reports fixture -- mesma forma de priced_bc_<país>_<data>.csv
    (meeting_date/implied_change_bps/cumulative_change_from_spot_bps), a
    fonte de verdade que build_lab_skeleton agora usa em vez de recomputar
    via curve.forward_rate (ver docstring do módulo)."""
    if implied_change_bps is None:
        implied_change_bps = [10.0] * len(meetings)
    cumulative, running = [], 0.0
    reports = []
    for m, chg in zip(meetings, implied_change_bps):
        running += chg
        reports.append({"meeting_date": m, "implied_change_bps": chg, "cumulative_change_from_spot_bps": running})
        cumulative.append(running)
    return reports


def test_skeleton_has_one_meeting_entry_per_meeting_with_correct_tau():
    curve = _curve(MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")

    assert [m["date"] for m in skeleton["meetings"]] == [d.isoformat() for d in MEETINGS]
    assert skeleton["meetings"][0]["tau"] == pytest.approx(curve.tau(VALUATION_DATE, MEETINGS[0]))
    assert skeleton["meetings"][1]["tau"] == pytest.approx(curve.tau(MEETINGS[0], MEETINGS[1]))


def test_meeting_market_fields_come_from_report_not_recomputed_from_curve():
    """Regression (Ricardo, 29/07/2026): a tabela de cards e a de cenários
    interativos mostravam bps/taxa diferentes pra mesma reunião porque essa
    função recomputava via curve.forward_rate, ignorando o priced_bc CSV
    (que pode vir de NSS, split 65/35 ou FRA direto, nunca forward_rate
    puro). Agora market_change_bps/market_forward_pct têm que ser um
    pass-through exato do relatório -- inclusive quando isso diverge muito
    do que a curva "crua" implicaria (curva flat nesse teste: forward_rate
    daria 0bps em toda reunião, mas o relatório sintético abaixo diz outra
    coisa, e é isso que tem que aparecer no skeleton)."""
    curve = _curve(MEETINGS, rate=0.10)  # curva flat -- forward_rate cru daria 0bps sempre
    reports = _reports(implied_change_bps=[-17.0, 8.0, 25.0])

    skeleton = build_lab_skeleton(curve, reports, current_policy_rate=0.095, country="chile")

    assert skeleton["meetings"][0]["market_change_bps"] == pytest.approx(-17.0)
    assert skeleton["meetings"][1]["market_change_bps"] == pytest.approx(8.0)
    assert skeleton["meetings"][2]["market_change_bps"] == pytest.approx(25.0)
    # market_forward_pct = current_policy_rate + cumulative_change_from_spot_bps
    assert skeleton["meetings"][0]["market_forward_pct"] == pytest.approx(9.5 - 0.17)
    assert skeleton["meetings"][1]["market_forward_pct"] == pytest.approx(9.5 - 0.17 + 0.08)
    assert skeleton["meetings"][2]["market_forward_pct"] == pytest.approx(9.5 - 0.17 + 0.08 + 0.25)


def test_skeleton_top_level_fields():
    curve = _curve(MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")
    assert skeleton["valuation_date"] == VALUATION_DATE.isoformat()
    assert skeleton["compounding"] == "exponential"
    assert skeleton["current_policy_rate_pct"] == pytest.approx(9.5)


def test_vertex_within_horizon_gets_segment_index_and_local_tau():
    # vértice cai dentro do 2º segmento (entre a 1ª e a 2ª reunião)
    vertex_date = date(2026, 4, 1)
    curve = _curve([vertex_date] + MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")

    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["segment_index"] == 2  # boundary_dates = [val, m0, m1, m2] -- m1 é o índice 2
    assert entry["tau_from_segment_start"] == pytest.approx(curve.tau(MEETINGS[0], vertex_date))
    assert "tail_tau" not in entry


def test_vertex_beyond_last_meeting_gets_tail_fields():
    vertex_date = date(2027, 1, 1)  # depois da última reunião (2026-06-01)
    curve = _curve([vertex_date] + MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")

    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["segment_index"] is None
    assert entry["tail_tau"] == pytest.approx(curve.tau(MEETINGS[-1], vertex_date))
    assert entry["tail_base_forward_pct"] == pytest.approx(curve.forward_rate(MEETINGS[-1], vertex_date) * 100)


def test_vertex_market_zero_matches_curve_directly():
    vertex_date = MEETINGS[1]
    curve = _curve([vertex_date] + MEETINGS, rate=0.12)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")
    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["market_zero_pct"] == pytest.approx(curve.zero_rate(vertex_date) * 100)


def test_raises_when_no_meetings_given():
    curve = _curve(MEETINGS)
    with pytest.raises(ValueError, match="pelo menos 1 reunião"):
        build_lab_skeleton(curve, [], current_policy_rate=0.095, country="chile")


def test_vertex_label_is_di1_contract_code_for_brazil():
    """Ricardo (29/07/2026): quer o 'nome' do vértice (código do DI1 pro
    Brasil) ao lado do vencimento na tabela de impacto."""
    vertex_date = date(2027, 1, 4)  # 1o dia útil de jan/2027 -> contrato F27
    curve = _curve([vertex_date] + MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="brazil")
    entry = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_date.isoformat())
    assert entry["label"] == "DIF27"


def test_vertex_label_is_generic_tenor_for_non_brazil_countries():
    """Pros demais países (sem código de contrato próprio), o 'nome' é um
    tenor aproximado (3M, 18M, 2Y, ...) contado a partir da data de
    valuation."""
    vertex_3m = date(2026, 4, 6)  # ~3 meses depois de 2026-01-05
    vertex_2y = date(2028, 1, 5)  # exatamente 2 anos depois
    curve = _curve([vertex_3m, vertex_2y] + MEETINGS)
    skeleton = build_lab_skeleton(curve, _reports(), current_policy_rate=0.095, country="chile")

    entry_3m = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_3m.isoformat())
    entry_2y = next(v for v in skeleton["vertices"] if v["maturity"] == vertex_2y.isoformat())
    assert entry_3m["label"] == "3M"
    assert entry_2y["label"] == "2Y"
