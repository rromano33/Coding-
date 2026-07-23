"""VaR (histórico e paramétrico) e vol a partir de uma série de P&L diário
do portfólio. VaR é sempre de 1 dia -- o que muda entre "3M" e "12M" é a
janela de estimação (quantos dias de P&L histórico entram na amostra), não
o horizonte do VaR em si."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class RiskMetrics:
    confidence: float
    n_obs: int
    var_historical: float   # $ em risco (positivo = perda); negativo só é possível se a amostra não tiver risco de perda naquele quantil
    var_parametric: float
    daily_vol: float        # desvio-padrão do P&L diário, em $
    annualized_vol: float   # daily_vol * sqrt(trading_days_per_year)


def historical_var(pnl, confidence: float) -> float:
    """Perda no quantil (1-confidence) da distribuição empírica do P&L."""
    quantile_pnl = np.percentile(np.asarray(pnl, dtype=float), (1 - confidence) * 100)
    return -float(quantile_pnl)


def parametric_var(pnl, confidence: float) -> float:
    """Variância-covariância: assume P&L diário ~ Normal(mean, std)."""
    pnl = np.asarray(pnl, dtype=float)
    mean = pnl.mean()
    std = pnl.std(ddof=1)
    z = norm.ppf(1 - confidence)  # negativo, ex: -1.645 para 95%
    return -float(mean + z * std)


def risk_metrics(pnl, confidence: float, trading_days_per_year: int = 252) -> RiskMetrics:
    pnl = np.asarray(pnl, dtype=float)
    daily_vol = float(pnl.std(ddof=1))
    return RiskMetrics(
        confidence=confidence,
        n_obs=len(pnl),
        var_historical=historical_var(pnl, confidence),
        var_parametric=parametric_var(pnl, confidence),
        daily_vol=daily_vol,
        annualized_vol=daily_vol * (trading_days_per_year ** 0.5),
    )
