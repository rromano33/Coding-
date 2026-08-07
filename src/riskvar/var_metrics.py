"""VaR (histórico e paramétrico), Expected Shortfall e vol a partir de uma
série de P&L diário do portfólio. VaR/ES são sempre de 1 dia -- o que muda
entre "3M" e "12M" é a janela de estimação (quantos dias de P&L histórico
entram na amostra), não o horizonte em si."""
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
    es_historical: float    # Expected Shortfall (CVaR): perda média ALÉM do VaR -- captura o tamanho da cauda, não só o ponto de corte
    es_parametric: float
    daily_vol: float        # desvio-padrão do P&L diário, em $
    annualized_vol: float   # daily_vol * sqrt(trading_days_per_year)
    n_breaches_historical: int    # dias em que a perda real ultrapassou o VaR histórico
    n_breaches_parametric: int    # dias em que a perda real ultrapassou o VaR paramétrico
    expected_breaches: float      # n_obs * (1 - confidence) -- referência teórica pra comparar com os dois acima


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


def historical_es(pnl, confidence: float) -> float:
    """Expected Shortfall histórico: perda MÉDIA entre os dias que caem no
    quantil de cauda (1-confidence) ou além dele -- ao contrário do VaR
    (só o ponto de corte), captura o quão ruim a cauda é, não só a
    probabilidade de estourar. Padrão de referência do FRTB (Basel), que
    substituiu VaR por ES como métrica regulatória principal."""
    pnl = np.asarray(pnl, dtype=float)
    threshold = np.percentile(pnl, (1 - confidence) * 100)
    tail = pnl[pnl <= threshold]
    if len(tail) == 0:  # pragma: no cover -- só com amostra degenerada (1 obs)
        tail = pnl
    return -float(tail.mean())


def parametric_es(pnl, confidence: float) -> float:
    """Expected Shortfall paramétrico: fórmula fechada pra Normal(mean, std)
    -- E[pnl | pnl <= quantil] = mean - std * phi(z) / (1-confidence), onde
    phi é a densidade normal padrão e z = norm.ppf(1-confidence). Sempre
    >= VaR paramétrico pra qualquer confiança (a cauda além do corte nunca
    é menos severa que o corte em si)."""
    pnl = np.asarray(pnl, dtype=float)
    mean = pnl.mean()
    std = pnl.std(ddof=1)
    alpha = 1 - confidence
    z = norm.ppf(alpha)
    es_pnl = mean - std * norm.pdf(z) / alpha
    return -float(es_pnl)


def count_breaches(pnl, var_estimate: float) -> int:
    """Quantos dias a perda real (-pnl) ultrapassou o VaR estimado --
    checagem em-amostra (não é um backtest walk-forward de verdade, que
    precisaria reestimar o VaR em cada dia histórico com os dados até ali;
    isso aqui compara o VaR de UMA estimativa contra a mesma amostra que a
    gerou). Pra VaR histórico isso é quase tautológico (por definição, ~
    (1-confidence) da amostra cai abaixo do quantil que definiu o próprio
    VaR) -- o valor real está em comparar contra o VaR PARAMÉTRICO: se o
    número de estouros for bem maior que o esperado, é sinal de que a
    distribuição real tem caudas mais gordas do que a Normal assume."""
    pnl = np.asarray(pnl, dtype=float)
    losses = -pnl
    return int((losses > var_estimate).sum())


def risk_metrics(pnl, confidence: float, trading_days_per_year: int = 252) -> RiskMetrics:
    pnl = np.asarray(pnl, dtype=float)
    daily_vol = float(pnl.std(ddof=1))
    var_hist = historical_var(pnl, confidence)
    var_param = parametric_var(pnl, confidence)
    return RiskMetrics(
        confidence=confidence,
        n_obs=len(pnl),
        var_historical=var_hist,
        var_parametric=var_param,
        es_historical=historical_es(pnl, confidence),
        es_parametric=parametric_es(pnl, confidence),
        daily_vol=daily_vol,
        annualized_vol=daily_vol * (trading_days_per_year ** 0.5),
        n_breaches_historical=count_breaches(pnl, var_hist),
        n_breaches_parametric=count_breaches(pnl, var_param),
        expected_breaches=len(pnl) * (1 - confidence),
    )
