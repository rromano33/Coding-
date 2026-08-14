"""Dimensionamento de posição ajustado por volatilidade realizada -- motor
de cálculo puro (sem Streamlit/UI) por trás de streamlit_app/sizing_tool.py,
igual ao resto do riskvar separa a matemática (aqui) da apresentação (lá).

Ideia: dado um preço de entrada, um stop em múltiplos de desvio-padrão da
variação diária (não em % fixo arbitrário -- adapta ao regime de vol atual
do ativo) e uma perda máxima aceita em $, back-calcula o tamanho de
posição (Notional ou DV01) tal que, SE o stop for atingido, a perda seja
exatamente a perda máxima informada.

Duas convenções de "kind" (mesma distinção de
riskvar.pnl_series.position_pnl_series -- notional vs dv01):
- "pct": preço é um nível (FX, ação, futuro) -- variações em % do preço.
- "bps": preço é uma taxa/yield cotada em % -- variações em bps
  (diff(nível)*100, mesma convenção do resto do projeto)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def change_series(prices: pd.Series, kind: str) -> pd.Series:
    """Série de variações diárias na unidade do `kind`: % (kind="pct") ou
    bps (kind="bps"). Mesma convenção de riskvar.stress.factor_change_series,
    reexpressa aqui em % (não decimal) porque é assim que a ferramenta de
    sizing mostra os números (ex: "0.42%", não "0.0042")."""
    prices = prices.dropna()
    if kind == "pct":
        return prices.pct_change().dropna() * 100.0
    if kind == "bps":
        return prices.diff().dropna() * 100.0
    raise ValueError(f"kind desconhecido: {kind!r} (use 'pct' ou 'bps')")


@dataclass(frozen=True)
class VolStats:
    n_obs: int
    daily_vol: float          # desvio-padrão da variação diária, na unidade do kind (% ou bps)
    annualized_vol: float     # daily_vol * sqrt(trading_days_per_year)
    mean: float
    median: float
    skew: float
    excess_kurtosis: float


def vol_stats(changes: pd.Series, trading_days_per_year: int = 252) -> VolStats:
    arr = np.asarray(changes, dtype=float)
    daily_vol = float(arr.std(ddof=1))
    mean = float(arr.mean())
    median = float(np.median(arr))
    std = daily_vol if daily_vol else 1.0
    skew = float(np.mean(((arr - mean) / std) ** 3)) if daily_vol else 0.0
    excess_kurtosis = float(np.mean(((arr - mean) / std) ** 4) - 3) if daily_vol else 0.0
    return VolStats(
        n_obs=len(arr),
        daily_vol=daily_vol,
        annualized_vol=daily_vol * (trading_days_per_year ** 0.5),
        mean=mean,
        median=median,
        skew=skew,
        excess_kurtosis=excess_kurtosis,
    )


def vol_stats_by_window(changes: pd.Series, windows: dict[str, int], trading_days_per_year: int = 252) -> pd.DataFrame:
    """Uma linha por janela (ex: {"7D": 7, "15D": 15, "30D": 30, "60D": 60}),
    com vol anualizada, vol diária, variação média, variação acumulada e
    extremos -- mesmas colunas da tabela "Window / Ann.Vol / Daily σ / Avg
    Move / Cum Move / Max 1D / Min 1D" da ferramenta original."""
    rows = []
    for label, n_days in windows.items():
        window = changes.tail(n_days)
        if window.empty:
            continue
        stats = vol_stats(window, trading_days_per_year)
        rows.append({
            "janela": label,
            "vol_anualizada": stats.annualized_vol,
            "vol_diaria": stats.daily_vol,
            "variacao_media": float(window.mean()),
            "variacao_acumulada": float(window.sum()),
            "max_1d": float(window.max()),
            "min_1d": float(window.min()),
        })
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class SizingResult:
    size: float               # Notional ($) ou DV01 ($/bp), conforme size_output
    stop_move: float          # distância do stop em relação à entrada, na unidade do kind (% ou bps)
    stop_price: float
    target_price: float


def size_position(
    trade_price: float,
    daily_vol: float,
    stop_multiple: float,
    reward_risk: float,
    max_loss: float,
    side: str,
    kind: str,
) -> SizingResult:
    """Back-calcula o tamanho da posição tal que perder exatamente
    `max_loss` seja o resultado de o preço andar `stop_multiple` desvios-
    padrão CONTRA a posição. `kind` decide tanto a unidade do movimento
    quanto o TIPO de tamanho devolvido (mesmo acoplamento de
    riskvar.pnl_series.position_pnl_series: não faz sentido pedir DV01 de
    um ativo cotado em nível, nem Notional de uma taxa):

    - kind="pct" (preço é nível -- FX, ação, futuro) -> `size` é Notional
      ($): perda no stop = size * (stop_move/100).
    - kind="bps" (preço é taxa/yield cotada em %) -> `size` é DV01 ($/bp):
      perda no stop = size * stop_move (stop_move em bps). Mesma
      convenção de sinal/unidade de position_pnl_series (dv01 * diff_bps).

    stop_move = stop_multiple * daily_vol (sempre positivo, mesma unidade
    do kind). side="long": stop abaixo da entrada, target acima (e
    vice-versa pra "short"). target = entrada +/- reward_risk *
    distância_do_stop."""
    if side not in ("long", "short"):
        raise ValueError(f"side inválido: {side!r} (use 'long' ou 'short')")
    if kind not in ("pct", "bps"):
        raise ValueError(f"kind inválido: {kind!r} (use 'pct' ou 'bps')")

    stop_move = stop_multiple * daily_vol  # sempre positivo (distância)

    if kind == "pct":
        price_distance = trade_price * (stop_move / 100.0)
        size = max_loss / (stop_move / 100.0) if stop_move else 0.0
    else:
        price_distance = stop_move / 100.0  # bps -> pontos percentuais de taxa
        size = max_loss / stop_move if stop_move else 0.0

    if side == "long":
        stop_price = trade_price - price_distance
        target_price = trade_price + reward_risk * price_distance
    else:
        stop_price = trade_price + price_distance
        target_price = trade_price - reward_risk * price_distance

    return SizingResult(size=size, stop_move=stop_move, stop_price=stop_price, target_price=target_price)
