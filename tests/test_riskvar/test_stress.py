from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from riskvar.stress import factor_change_series, fit_factor_sensitivities, run_stress_scenarios


def _series(values: list[float], start=date(2026, 1, 1)) -> pd.Series:
    dates = [start + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=pd.to_datetime(dates))


def test_factor_change_series_pct_return_matches_pct_change():
    prices = _series([100.0, 102.0, 99.0])
    change = factor_change_series(prices, kind="pct_return")
    assert change.iloc[0] == pytest.approx(0.02)
    assert change.iloc[1] == pytest.approx(99.0 / 102.0 - 1)


def test_factor_change_series_bps_change_matches_diff_times_100():
    yields_pct = _series([4.50, 4.55, 4.40])
    change = factor_change_series(yields_pct, kind="bps_change")
    assert change.iloc[0] == pytest.approx(5.0)
    assert change.iloc[1] == pytest.approx(-15.0)


def test_factor_change_series_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind de fator desconhecido"):
        factor_change_series(_series([1.0, 2.0]), kind="whatever")


def test_fit_factor_sensitivities_recovers_known_linear_betas_exactly():
    # P&L construído como combinação linear EXATA de 2 fatores, sem ruído
    # -- a regressão precisa recuperar os betas com precisão de máquina.
    n = 50
    rng = np.random.default_rng(0)
    spx_return = rng.normal(0, 0.01, n)
    ust_bps = rng.normal(0, 3.0, n)
    true_beta_spx = 2_000_000.0   # $ de P&L por 1.0 (100%) de retorno do SPX
    true_beta_ust = -50_000.0     # $ de P&L por 1bp de alta na UST10y
    pnl_values = true_beta_spx * spx_return + true_beta_ust * ust_bps

    pnl = _series(list(pnl_values))
    factors = {"spx": _series(list(spx_return)), "ust10y": _series(list(ust_bps))}

    betas, r_squared = fit_factor_sensitivities(pnl, factors)

    assert betas["spx"] == pytest.approx(true_beta_spx, rel=1e-6)
    assert betas["ust10y"] == pytest.approx(true_beta_ust, rel=1e-6)
    assert r_squared == pytest.approx(1.0, abs=1e-6)  # sem ruído -- ajuste perfeito


def test_fit_factor_sensitivities_raises_when_too_few_aligned_observations():
    pnl = _series([1.0, 2.0])
    factors = {"spx": _series([0.01, 0.02]), "ust10y": _series([1.0, 2.0])}
    with pytest.raises(ValueError, match="histórico em comum insuficiente"):
        fit_factor_sensitivities(pnl, factors)


def test_fit_factor_sensitivities_rejects_empty_factors():
    with pytest.raises(ValueError, match="pelo menos 1 fator"):
        fit_factor_sensitivities(_series([1.0, 2.0, 3.0]), {})


def test_run_stress_scenarios_applies_shocks_linearly_on_known_betas():
    n = 60
    rng = np.random.default_rng(1)
    spx_return = rng.normal(0, 0.01, n)
    ust_bps = rng.normal(0, 3.0, n)
    true_beta_spx = 1_500_000.0
    true_beta_ust = -30_000.0
    pnl = _series(list(true_beta_spx * spx_return + true_beta_ust * ust_bps))
    factors = {"spx": _series(list(spx_return)), "ust10y": _series(list(ust_bps))}

    scenarios = [
        {"name": "S&P -5%", "shocks": {"spx": -0.05}},
        {"name": "UST10y +20bps", "shocks": {"ust10y": 20}},
        {"name": "Risk-off combinado", "shocks": {"spx": -0.05, "ust10y": 20}},
    ]
    results = run_stress_scenarios(pnl, factors, scenarios)

    by_name = {r.name: r for r in results}
    assert by_name["S&P -5%"].pnl_impact == pytest.approx(true_beta_spx * -0.05, rel=1e-5)
    assert by_name["UST10y +20bps"].pnl_impact == pytest.approx(true_beta_ust * 20, rel=1e-5)
    # cenário combinado é a soma linear dos dois choques individuais
    assert by_name["Risk-off combinado"].pnl_impact == pytest.approx(
        by_name["S&P -5%"].pnl_impact + by_name["UST10y +20bps"].pnl_impact, rel=1e-5
    )
    assert all(r.r_squared == pytest.approx(1.0, abs=1e-6) for r in results)


def test_run_stress_scenarios_ignores_factor_not_present_in_fit():
    pnl = _series([10.0, -20.0, 15.0, -5.0, 8.0])
    factors = {"spx": _series([0.01, -0.02, 0.015, -0.005, 0.008])}
    scenarios = [{"name": "Fator desconhecido", "shocks": {"nao_existe": 999}}]
    results = run_stress_scenarios(pnl, factors, scenarios)
    assert results[0].pnl_impact == 0.0
