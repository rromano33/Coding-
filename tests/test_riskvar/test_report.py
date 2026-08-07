import numpy as np
import pandas as pd
import pytest

from riskvar.report import build_risk_report


def test_build_risk_report_has_one_row_per_window_times_confidence():
    rng = np.random.default_rng(0)
    pnl_by_window = {
        "3M": pd.Series(rng.normal(0, 100, 63)),
        "12M": pd.Series(rng.normal(0, 100, 252)),
    }
    df = build_risk_report(pnl_by_window, confidence_levels=[0.95, 0.99])
    assert len(df) == 4  # 2 janelas x 2 confianças
    assert set(df["janela"]) == {"3M", "12M"}
    assert set(df["confianca"]) == {"95%", "99%"}


def test_build_risk_report_includes_es_and_breach_columns():
    pnl_by_window = {"3M": pd.Series(np.random.default_rng(1).normal(0, 100, 100))}
    df = build_risk_report(pnl_by_window, confidence_levels=[0.95])
    row = df.iloc[0]
    assert row["es_historico"] >= row["var_historico"]
    assert row["es_parametrico"] >= row["var_parametrico"]
    assert row["breaches_esperados"] == pytest.approx(100 * 0.05)
    assert "n_breaches_historico" in df.columns
    assert "n_breaches_parametrico" in df.columns
