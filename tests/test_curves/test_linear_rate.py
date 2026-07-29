from datetime import date

import pytest

from emrates.central_banks.stripper import strip_meeting_path
from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import Pillar
from emrates.curves.linear_rate import build_linear_rate_curve
from emrates.curves.nss import fit_nss_curve
from emrates.curves.factory import build_curve_builder, load_country_config
from emrates.data.calendars import Calendar

VALUATION_DATE = date(2026, 7, 29)
CALENDAR = Calendar("mexico", holidays=set())

# Tickers/taxas reais da planilha MXN TIIE do Ricardo (29/07/2026, print de
# tela) -- mesmos dados usados pra achar essa curva mais simples.
MXN_PILLARS = [
    Pillar(maturity=date(2026, 10, 22), rate=0.0656),
    Pillar(maturity=date(2027, 1, 14), rate=0.0662),
    Pillar(maturity=date(2027, 4, 8), rate=0.0669),
    Pillar(maturity=date(2027, 7, 29), rate=0.0682),
    Pillar(maturity=date(2028, 7, 27), rate=0.0726),
    Pillar(maturity=date(2029, 7, 26), rate=0.0757),
    Pillar(maturity=date(2031, 7, 24), rate=0.0791),
    Pillar(maturity=date(2036, 7, 17), rate=0.0836),
]
MXN_CURRENT_POLICY_RATE = 0.0650
MXN_MEETINGS = [
    date(2026, 8, 6), date(2026, 9, 24), date(2026, 11, 5), date(2026, 12, 17),
    date(2027, 2, 4), date(2027, 3, 25), date(2027, 5, 13), date(2027, 6, 24),
    date(2027, 8, 5), date(2027, 9, 23), date(2027, 11, 4), date(2027, 12, 16),
    date(2028, 2, 3),  # +1 extra pra strip_meeting_path conseguir ler a última
]
# Coluna "Mkt" da planilha do Ricardo -- bps precificados por reunião.
MXN_REFERENCE_BPS = [1.5, 5, 6, 2, 10, 8, 9, 10, 10, 10, 15, 10]


def test_forward_rate_matches_manual_linear_interpolation_between_pillars():
    curve = build_linear_rate_curve(
        VALUATION_DATE,
        [Pillar(maturity=date(2027, 1, 29), rate=0.06), Pillar(maturity=date(2028, 1, 29), rate=0.08)],
        DayCount.ACT_360,
        Compounding.EXPONENTIAL,
        CALENDAR,
    )
    midpoint = date(2027, 7, 29)  # a meio caminho entre os dois pilares
    tau_first = curve.tau(VALUATION_DATE, date(2027, 1, 29))
    tau_mid = curve.tau(VALUATION_DATE, midpoint)
    tau_last = curve.tau(VALUATION_DATE, date(2028, 1, 29))
    weight = (tau_mid - tau_first) / (tau_last - tau_first)
    expected_zero_rate = 0.06 + weight * (0.08 - 0.06)
    # DF(midpoint) implícito por essa taxa zero interpolada deve bater com
    # forward_rate(valuation, midpoint) reconstruído a partir dele.
    expected_df = (1 + expected_zero_rate) ** (-tau_mid)
    actual_df = curve.discount_factor(midpoint)
    assert actual_df == pytest.approx(expected_df, rel=1e-6)


def test_clamps_to_edge_rates_outside_pillar_range():
    curve = build_linear_rate_curve(
        VALUATION_DATE,
        [Pillar(maturity=date(2027, 1, 29), rate=0.06), Pillar(maturity=date(2028, 1, 29), rate=0.08)],
        DayCount.ACT_360,
        Compounding.EXPONENTIAL,
        CALENDAR,
    )
    assert curve._zero_rate(0.01) == pytest.approx(0.06)  # antes do 1o pilar
    assert curve._zero_rate(100.0) == pytest.approx(0.08)  # depois do último


def test_raises_when_no_pillars():
    with pytest.raises(ValueError, match="pelo menos 1 pilar"):
        build_linear_rate_curve(VALUATION_DATE, [], DayCount.ACT_360, Compounding.EXPONENTIAL, CALENDAR)


def test_reproduces_real_mxn_case_much_closer_than_nss_or_exact_bootstrap():
    """Regression (Ricardo, 29/07/2026): comparando contra a curva de TIIE
    real dele no Bloomberg (mesmos tickers/taxas acima), tanto a curva exata
    (bootstrap de cupom) quanto o NSS divergiam ~26-28bps acumulados até
    dez/27 -- e o split 65/35 (estilo Colômbia) divergia ~55bps. Interpolação
    linear direto na taxa, sem bootstrap, chegou a ~13.6bps de diferença --
    ainda não perfeito, mas MUITO mais perto. Esse teste trava esse ganho."""
    cfg = load_country_config("mexico")
    exact_curve = build_curve_builder(cfg, CALENDAR).build(VALUATION_DATE, MXN_PILLARS)
    smoothed_curve = fit_nss_curve(exact_curve)
    linear_curve = build_linear_rate_curve(
        VALUATION_DATE, MXN_PILLARS, DayCount(cfg["day_count"]), Compounding(cfg["compounding"]), CALENDAR
    )

    def final_cum_diff(curve) -> float:
        results = strip_meeting_path(curve, MXN_MEETINGS, MXN_CURRENT_POLICY_RATE)
        our_cum = sum(r.implied_change_bps for r in results)
        reference_cum = sum(MXN_REFERENCE_BPS)
        return our_cum - reference_cum

    nss_diff = final_cum_diff(smoothed_curve)
    linear_diff = final_cum_diff(linear_curve)

    assert abs(nss_diff) > 20  # o problema que motivou a mudança
    assert abs(linear_diff) < 20  # bem melhor, ainda que não perfeito
    assert abs(linear_diff) < abs(nss_diff)
