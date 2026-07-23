import numpy as np
import pytest

from riskvar.var_metrics import historical_var, parametric_var, risk_metrics


def test_historical_var_matches_numpy_percentile_directly():
    pnl = list(range(-100, 100))  # -100..99, 200 pontos igualmente espaçados
    expected = -float(np.percentile(pnl, 5))
    assert historical_var(pnl, confidence=0.95) == pytest.approx(expected, abs=1e-9)


def test_parametric_var_matches_gaussian_formula_on_known_mean_std():
    rng = np.random.default_rng(0)
    pnl = rng.normal(loc=1000, scale=500, size=5000)
    var = parametric_var(pnl, confidence=0.95)
    expected = 1.645 * 500 - 1000  # z(95%) ~= -1.645, VaR = -(mean + z*std)
    assert var == pytest.approx(expected, rel=0.1)


def test_flat_pnl_has_zero_vol_and_negative_var_no_loss_risk():
    pnl = [10.0] * 50
    m = risk_metrics(pnl, confidence=0.95)
    assert m.daily_vol == pytest.approx(0.0, abs=1e-9)
    # sem variação nenhuma dia a dia -- "VaR" negativo == ganho garantido, não risco de perda
    assert m.var_historical == pytest.approx(-10.0, abs=1e-6)
    assert m.var_parametric == pytest.approx(-10.0, abs=1e-6)


def test_annualized_vol_scales_by_sqrt_trading_days():
    rng = np.random.default_rng(1)
    pnl = rng.normal(0, 100, 300)
    m = risk_metrics(pnl, confidence=0.95, trading_days_per_year=252)
    assert m.annualized_vol == pytest.approx(m.daily_vol * (252 ** 0.5), rel=1e-9)


def test_higher_confidence_means_larger_var():
    rng = np.random.default_rng(2)
    pnl = rng.normal(0, 100, 1000)
    var_95 = historical_var(pnl, 0.95)
    var_99 = historical_var(pnl, 0.99)
    assert var_99 > var_95
