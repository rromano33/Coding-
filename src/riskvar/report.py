"""Monta a tabela final: uma linha por (janela, confiança), com VaR
histórico, VaR paramétrico, Expected Shortfall (histórico e paramétrico),
vol (diária e anualizada) e contagem de estouros (backtest em-amostra --
ver var_metrics.count_breaches)."""
from __future__ import annotations

import pandas as pd

from riskvar.var_metrics import risk_metrics


def build_risk_report(
    pnl_by_window: dict[str, pd.Series],
    confidence_levels: list[float],
    trading_days_per_year: int = 252,
) -> pd.DataFrame:
    rows = []
    for window_label, pnl in pnl_by_window.items():
        for confidence in confidence_levels:
            m = risk_metrics(pnl.values, confidence, trading_days_per_year)
            rows.append(
                {
                    "janela": window_label,
                    "confianca": f"{confidence:.0%}",
                    "n_obs": m.n_obs,
                    "var_historico": m.var_historical,
                    "var_parametrico": m.var_parametric,
                    "es_historico": m.es_historical,
                    "es_parametrico": m.es_parametric,
                    "vol_diaria": m.daily_vol,
                    "vol_anualizada": m.annualized_vol,
                    "n_breaches_historico": m.n_breaches_historical,
                    "n_breaches_parametrico": m.n_breaches_parametric,
                    "breaches_esperados": m.expected_breaches,
                }
            )
    return pd.DataFrame(rows)
