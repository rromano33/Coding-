"""Monta a tabela final: uma linha por (janela, confiança), com VaR
histórico, VaR paramétrico e vol (diária e anualizada)."""
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
                    "vol_diaria": m.daily_vol,
                    "vol_anualizada": m.annualized_vol,
                }
            )
    return pd.DataFrame(rows)
