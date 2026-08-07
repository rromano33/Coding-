import numpy as np
import pytest

from riskvar.var_metrics import (
    count_breaches,
    historical_es,
    historical_var,
    parametric_es,
    parametric_var,
    risk_metrics,
)


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


def test_historical_es_is_average_of_tail_beyond_var():
    # cauda inferior conhecida na mão: os 5 piores de 100 pontos igualmente
    # espaçados de -50 a 49 -- P5 cai exatamente no 5o pior valor.
    pnl = list(range(-50, 50))
    var = historical_var(pnl, confidence=0.95)
    es = historical_es(pnl, confidence=0.95)
    worst_5 = sorted(pnl)[:5]
    assert es == pytest.approx(-float(np.mean(worst_5)), abs=1e-6)
    assert es >= var  # ES nunca é menos severo que o VaR


def test_parametric_es_matches_known_gaussian_multiplier_at_95pct():
    # ES_95% de uma Normal(0, sigma) é ~2.063*sigma (multiplicador padrão de mercado)
    rng = np.random.default_rng(3)
    pnl = rng.normal(loc=0.0, scale=1000.0, size=20000)
    es = parametric_es(pnl, confidence=0.95)
    assert es == pytest.approx(2.063 * 1000.0, rel=0.05)


def test_parametric_es_always_at_least_parametric_var():
    rng = np.random.default_rng(4)
    pnl = rng.normal(500, 300, 2000)
    for confidence in (0.90, 0.95, 0.99):
        assert parametric_es(pnl, confidence) >= parametric_var(pnl, confidence)


def test_count_breaches_counts_losses_strictly_beyond_var():
    pnl = [-200, -150, -50, 0, 50, 100]
    # perdas: 200, 150, 50, 0(sem perda), -50(ganho), -100(ganho)
    assert count_breaches(pnl, var_estimate=100) == 2  # 200 e 150 > 100
    assert count_breaches(pnl, var_estimate=200) == 0  # nenhuma perda ultrapassa 200
    assert count_breaches(pnl, var_estimate=0) == 3    # 200, 150 e 50 > 0


def test_risk_metrics_includes_es_and_breach_fields():
    rng = np.random.default_rng(5)
    pnl = rng.normal(0, 100, 500)
    m = risk_metrics(pnl, confidence=0.95)
    assert m.es_historical >= m.var_historical
    assert m.es_parametric >= m.var_parametric
    assert m.expected_breaches == pytest.approx(500 * 0.05)
    # VaR histórico é quase tautológico em-amostra -- deve ficar bem perto do esperado
    assert m.n_breaches_historical == pytest.approx(m.expected_breaches, abs=len(pnl) * 0.02)
