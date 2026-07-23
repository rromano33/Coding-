"""Lê o histórico diário de preços/taxas direto de uma aba da própria
planilha (ex: "Preços" em Data/Portfolio.xlsx), preenchida no Excel via
fórmula nativa da Bloomberg (=BDH(...)) -- sidesteps de vez a sessão
BBComm/xbbg em Python, que se mostrou instável (SessionConnectionDown/
SessionTerminated mesmo com poucos tickers e retry).

Layout esperado (linhas em branco entre o cabeçalho e os dados são
ignoradas; a posição exata das linhas de metadado é encontrada
procurando o rótulo, não por número fixo de linha):

    A            B          C          ...
    Start Date   01/01/2019
    End Date     23/07/2026

    Classe       Equity     FX         ...
    Ativo        ES1        AUDUSD     ...
    BBG          ES1 Index  AUDUSD Curncy ...
    01/jan/19    2505.25    0.71       ...
    02/jan/19    2511.00    0.7        ...
    ...

Cada coluna é uma série (um ticker); a linha "BBG" dá o ticker exato --
mesma string usada na coluna BBG da aba de posições (Summary), então o
merge entre posição e histórico é por igualdade direta de texto (com
strip(), sem normalização adicional). Células "#N/A N/A" (erro nativo do
Excel/Bloomberg quando não há cotação naquele dia -- feriado, ativo ainda
não existia etc.) viram NaN e são descartadas -- mesmo tratamento que
riskvar.pnl_series.position_pnl_series já dá a um buraco de cotação.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_price_history(path: str | Path, sheet: str, ticker_row_label: str = "BBG") -> dict[str, pd.Series]:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)

    label_col = raw.iloc[:, 0].astype(str).str.strip().str.lower()
    matches = label_col[label_col == ticker_row_label.strip().lower()].index
    if len(matches) == 0:
        raise KeyError(
            f"linha {ticker_row_label!r} não encontrada na coluna A da aba {sheet!r} -- "
            f"rótulos disponíveis: {label_col.tolist()}"
        )
    ticker_row_idx = matches[0]

    tickers_by_col = raw.iloc[ticker_row_idx, 1:]
    data = raw.iloc[ticker_row_idx + 1 :, :]

    dates = pd.to_datetime(data.iloc[:, 0], errors="coerce")
    valid_rows = dates.notna()
    dates = dates[valid_rows]
    data = data.loc[valid_rows]

    histories: dict[str, pd.Series] = {}
    for col_idx, ticker in tickers_by_col.items():
        if pd.isna(ticker):
            continue
        ticker = str(ticker).strip()
        values = pd.to_numeric(data[col_idx], errors="coerce")  # "#N/A N/A" -> NaN
        series = pd.Series(values.values, index=dates.values).dropna().sort_index()
        histories[ticker] = series
    return histories
