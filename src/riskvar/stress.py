"""Stress test por sensibilidade a fatores macro (ex: S&P 500, UST10y) --
diferente do VaR (estatístico, baseado na distribuição histórica), aqui a
pergunta é "e se um choque específico acontecer", medida via regressão
linear multi-fator do P&L do portfólio contra os fatores configurados.

Isso é DIFERENTE de cravar cenários de eventos históricos reais (Taper
Tantrum, COVID, etc.) -- aqueles precisam de pesquisa pra fixar magnitude/
data certas por evento; isso aqui é só sensibilidade estatística contínua
a fatores genéricos, então qualquer choque numérico (ex: "S&P -5%", "UST10y
+20bps") já é calculável direto, sem precisar de mais pesquisa.

Não depende de sessão Bloomberg em Python -- os fatores (ex: SPX Index,
USGG10YR Index) são lidos da MESMA aba "Preços" que já tem o histórico dos
ativos do portfólio (ver price_history.py), preenchida via =BDH(...) no
Excel. Basta adicionar o ticker do fator como mais uma linha nessa aba.

kind por fator (mesma convenção de PortfolioPosition.position_type):
- pct_return: fator é um preço/nível (ex: SPX Index) -- variação diária é
  retorno percentual.
- bps_change: fator é uma taxa/yield cotada em % (ex: USGG10YR Index) --
  variação diária é diff(nível)*100, em bps.

Os choques de cada cenário são especificados NA MESMA UNIDADE do fator
(ex: -0.05 pra SPX = -5%, 20 pra UST10y = +20bps)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def factor_change_series(prices: pd.Series, kind: str) -> pd.Series:
    prices = prices.dropna()
    if kind == "pct_return":
        return prices.pct_change().dropna()
    if kind == "bps_change":
        return prices.diff().dropna() * 100.0
    raise ValueError(f"kind de fator desconhecido: {kind!r} (use 'pct_return' ou 'bps_change')")


def fit_factor_sensitivities(pnl: pd.Series, factor_series: dict[str, pd.Series]) -> tuple[dict[str, float], float]:
    """Regressão linear (mínimos quadrados, com intercepto) do P&L contra
    TODOS os fatores simultaneamente -- não fator a fator isolado, pra não
    contar duas vezes o efeito de fatores que se movem juntos. Retorna
    (beta em $ por unidade de choque, para cada fator; R² da regressão).

    Alinha por data (interseção exata) -- fatores e P&L precisam ter
    histórico suficiente em comum."""
    if not factor_series:
        raise ValueError("fit_factor_sensitivities precisa de pelo menos 1 fator")
    frame = pd.DataFrame({"pnl": pnl, **factor_series}).dropna()
    if len(frame) < len(factor_series) + 2:
        raise ValueError(
            f"histórico em comum insuficiente pra ajustar {len(factor_series)} fator(es) "
            f"({len(frame)} dias alinhados) -- confira se os tickers dos fatores têm cotação "
            "nas mesmas datas do resto do portfólio."
        )
    factor_names = list(factor_series)
    design = np.column_stack([np.ones(len(frame))] + [frame[name].to_numpy() for name in factor_names])
    y = frame["pnl"].to_numpy()
    coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
    betas = coeffs[1:]

    fitted = design @ coeffs
    residual_ss = float(np.sum((y - fitted) ** 2))
    total_ss = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1 - residual_ss / total_ss if total_ss else 0.0

    return dict(zip(factor_names, betas)), r_squared


@dataclass(frozen=True)
class StressScenarioResult:
    name: str
    pnl_impact: float
    r_squared: float  # da regressão conjunta que gerou os betas -- baixo = fatores configurados explicam pouco do P&L desse book


def run_stress_scenarios(
    pnl: pd.Series, factor_series: dict[str, pd.Series], scenarios: list[dict]
) -> list[StressScenarioResult]:
    """scenarios: lista de {"name": str, "shocks": {factor_name: valor}}.
    Cada choque é aplicado na unidade do próprio fator (ver kind em
    factor_change_series). O impacto de cada cenário é a soma linear
    beta_i * choque_i -- todos os cenários usam a MESMA sensibilidade
    (ajustada uma vez só, com todos os fatores configurados juntos), não
    reestima a regressão por cenário."""
    betas, r_squared = fit_factor_sensitivities(pnl, factor_series)
    results = []
    for scenario in scenarios:
        impact = sum(betas.get(factor, 0.0) * shock for factor, shock in scenario["shocks"].items())
        results.append(StressScenarioResult(name=scenario["name"], pnl_impact=impact, r_squared=r_squared))
    return results
