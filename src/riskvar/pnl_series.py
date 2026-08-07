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

from dataclasses import dataclass

import pandas as pd

from riskvar.loader import PortfolioPosition
from riskvar.var_metrics import historical_var


def position_pnl_series(position: PortfolioPosition, price_history: pd.Series) -> pd.Series:
    prices = price_history.dropna()
    if position.position_type == "notional":
        daily_return = prices.pct_change().dropna()
        return position.position_value * daily_return
    daily_change_bps = prices.diff().dropna() * 100.0
    return position.position_value * daily_change_bps


def filter_positions_with_history(
    positions: list[PortfolioPosition], available_tickers
) -> tuple[list[PortfolioPosition], list[str]]:
    """Descarta posições cujo ticker a Bloomberg simplesmente não devolveu
    no histórico (bdh às vezes omite a coluna inteira em vez de vir cheia
    de NaN -- ticker sem dado nenhum no range pedido, par pouco líquido,
    erro de digitação na planilha etc.) em vez de deixar o resto do
    cálculo (portfolio_pnl_series) quebrar com KeyError. Quem chamar deve
    avisar o usuário sobre os tickers retornados em `missing`."""
    available = set(available_tickers)
    missing = sorted({p.ticker for p in positions if p.ticker not in available})
    kept = [p for p in positions if p.ticker not in missing]
    return kept, missing


def _aligned_position_pnl_frame(positions: list[PortfolioPosition], price_histories: dict[str, pd.Series]) -> pd.DataFrame:
    """Uma coluna de P&L diário por posição (índice = posição na lista de
    `positions`), alinhadas por data. Dias em que falta cotação para um
    ticker específico contam como 0 de P&L daquele ativo nesse dia (não
    derrubam a data inteira do portfólio) — simplificação razoável quando
    poucos ativos têm feriados descasados; se o book tiver calendários
    muito diferentes entre si, considere alinhar por interseção de datas
    em vez de união+fillna(0)."""
    series_list = [position_pnl_series(p, price_histories[p.ticker]).rename(i) for i, p in enumerate(positions)]
    return pd.concat(series_list, axis=1).fillna(0.0)


def portfolio_pnl_series(positions: list[PortfolioPosition], price_histories: dict[str, pd.Series]) -> pd.Series:
    """Soma as séries de P&L de cada posição, alinhadas por data."""
    return _aligned_position_pnl_frame(positions, price_histories).sum(axis=1)


def risk_contribution_pct(positions: list[PortfolioPosition], price_histories: dict[str, pd.Series]) -> list[float]:
    """% de participação de cada posição na variância do P&L do
    portfólio, via decomposição de Euler: beta_i = Cov(pnl_i, pnl_portfolio)
    / Var(pnl_portfolio).

    Soma exatamente 100% por construção -- P = soma das posições, então
    Cov(P,P) = Var(P) = soma das Cov(p_i,P), logo soma dos beta_i = 1.
    Não depende de normalidade nem do método de VaR (histórico ou
    paramétrico): é uma leitura de risco geral, baseada só na definição de
    portfólio como soma de posições. Um hedge de verdade (correlação
    negativa com o resto do book) aparece com contribuição NEGATIVA --
    reduz o risco do portfólio, não some do total.

    Se o portfólio não tiver variância nenhuma (todo mundo flat, ou só um
    dia de história), cai no fallback de dividir igualmente entre as
    posições -- não há como medir contribuição marginal sem variação."""
    if not positions:
        return []
    frame = _aligned_position_pnl_frame(positions, price_histories)
    portfolio = frame.sum(axis=1)
    portfolio_var = portfolio.var(ddof=1)
    if not portfolio_var:
        return [100.0 / len(positions)] * len(positions)
    return [(frame[i].cov(portfolio) / portfolio_var) * 100.0 for i in range(len(positions))]


@dataclass(frozen=True)
class DiversificationBenefit:
    standalone_var_sum: float  # soma dos VaRs de cada posição SOZINHA, como se cada uma fosse o portfólio inteiro
    portfolio_var: float       # VaR real do portfólio (net, com toda a correlação entre posições já embutida)
    benefit_pct: float         # 1 - portfolio_var/standalone_var_sum, em % -- quanto a diversificação "economiza"


def diversification_benefit(
    positions: list[PortfolioPosition], price_histories: dict[str, pd.Series], confidence: float
) -> DiversificationBenefit:
    """Soma dos VaRs "isolados" (cada posição como se fosse sozinha o
    portfólio inteiro) vs. o VaR real do portfólio (net) -- a diferença é
    o quanto a correlação entre as posições está reduzindo o risco total.
    Usa VaR histórico, na mesma amostra/janela das outras métricas do
    relatório.

    benefit_pct positivo = diversificação ajudando (comum, quando as
    posições não são perfeitamente correlacionadas). benefit_pct perto de
    zero ou negativo = posições andando muito juntas (pouca diversificação
    de verdade, ou hedges mal padronizados fazendo o net ficar maior que a
    soma das partes -- caso raro, mas possível com poucas observações)."""
    if not positions:
        return DiversificationBenefit(standalone_var_sum=0.0, portfolio_var=0.0, benefit_pct=0.0)
    frame = _aligned_position_pnl_frame(positions, price_histories)
    standalone_var_sum = sum(historical_var(frame[i], confidence) for i in range(len(positions)))
    portfolio_var = historical_var(frame.sum(axis=1), confidence)
    benefit_pct = (1 - portfolio_var / standalone_var_sum) * 100.0 if standalone_var_sum else 0.0
    return DiversificationBenefit(standalone_var_sum=standalone_var_sum, portfolio_var=portfolio_var, benefit_pct=benefit_pct)


def worst_days(pnl: pd.Series, n: int = 10) -> pd.DataFrame:
    """As N piores datas de P&L da série, perda maior primeiro -- contexto
    rápido de "o que aconteceu" sem abrir a série inteira."""
    worst = pnl.sort_values().head(n)
    return pd.DataFrame({"data": worst.index.date, "pnl": worst.values})
