"""Constrói a série histórica de P&L diário do portfólio a partir do
histórico de PX_LAST de cada ticker.

Duas convenções de posição (ver PortfolioPosition.position_type):

- notional: PX_LAST é um preço/nível (ação, FX, preço de bond, índice) —
  o retorno diário é percentual e o P&L do dia é position_value * retorno.

- dv01: PX_LAST é uma taxa/yield cotada em % (mesma convenção dos tickers
  de curva do projeto emrates — ex CDSWxx Curncy retornam a taxa em %
  como PX_LAST), então a variação diária em bps é diff(nível) * 100, e o
  P&L do dia é dv01 * variação_bps. O sinal do DV01 segue a MESMA
  convenção já usada em emrates.portfolio.risk.dv01: valor da posição
  para uma ALTA de 1bp na taxa. Se a posição ganha quando a taxa sobe
  (ex: pagador em swap / vendido em taxa), o DV01 informado na planilha
  deve ser positivo; se perde quando a taxa sobe (comprado em taxa),
  negativo.
"""
from __future__ import annotations

import pandas as pd

from riskvar.loader import PortfolioPosition


def position_pnl_series(position: PortfolioPosition, price_history: pd.Series) -> pd.Series:
    prices = price_history.dropna()
    if position.position_type == "notional":
        daily_return = prices.pct_change().dropna()
        return position.position_value * daily_return
    daily_change_bps = prices.diff().dropna() * 100.0
    return position.position_value * daily_change_bps


def portfolio_pnl_series(positions: list[PortfolioPosition], price_histories: dict[str, pd.Series]) -> pd.Series:
    """Soma as séries de P&L de cada posição, alinhadas por data. Dias em
    que falta cotação para um ticker específico contam como 0 de P&L
    daquele ativo nesse dia (não derrubam a data inteira do portfólio) —
    simplificação razoável quando poucos ativos têm feriados
    descasados; se o book tiver calendários muito diferentes entre si,
    considere alinhar por interseção de datas em vez de união+fillna(0)."""
    series_list = [position_pnl_series(p, price_histories[p.ticker]).rename(f"{p.asset}::{i}") for i, p in enumerate(positions)]
    combined = pd.concat(series_list, axis=1).fillna(0.0)
    return combined.sum(axis=1)
