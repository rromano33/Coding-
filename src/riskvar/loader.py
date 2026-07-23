"""Reads a portfolio spreadsheet: um ativo por linha, com ticker BBG e a
posição (notional em $ ou DV01 em $/bp). Layout configurável via
config/portfolio_risk.yaml (mesmo padrão de column_map usado em
emrates.data.excel_loader)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PortfolioPosition:
    asset: str
    ticker: str
    position_type: str  # "notional" ou "dv01" (normalizado em lowercase)
    position_value: float
    asset_class: str = "N/A"


class PortfolioLoader:
    def __init__(self, path: str | Path, sheet: str, column_map: dict):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} não encontrado — rode isso localmente, onde a planilha do portfólio está."
            )
        self.sheet = sheet
        self.column_map = column_map

    def _resolve_column(self, df: pd.DataFrame, key: str, required: bool = True) -> str | None:
        """Casa o nome configurado (config/portfolio_risk.yaml -> columns.<key>)
        contra o cabeçalho real da planilha ignorando maiúsculas/minúsculas e
        espaços nas pontas — mesmo padrão defensivo de
        emrates.data.excel_loader (cabeçalhos reais variam mais do que os
        exemplos usados pra configurar isso)."""
        wanted = self.column_map.get(key)
        if wanted is None:
            return None
        actual_by_normalized = {str(c).strip().lower(): c for c in df.columns}
        actual = actual_by_normalized.get(str(wanted).strip().lower())
        if actual is None and required:
            raise KeyError(
                f"coluna {wanted!r} (config: columns.{key}) não encontrada na aba {self.sheet!r} — "
                f"colunas disponíveis: {list(df.columns)}"
            )
        return actual

    def load(self) -> list[PortfolioPosition]:
        df = pd.read_excel(self.path, sheet_name=self.sheet)
        ticker_col = self._resolve_column(df, "ticker")
        asset_col = self._resolve_column(df, "asset")
        type_col = self._resolve_column(df, "position_type")
        value_col = self._resolve_column(df, "position_value")
        class_col = self._resolve_column(df, "asset_class", required=False)

        positions = []
        for _, row in df.iterrows():
            ticker = row[ticker_col]
            if pd.isna(ticker):
                continue
            raw_value = row[value_col]
            if pd.isna(raw_value) or float(raw_value) == 0.0:
                # Linha só de referência/watchlist (sem posição de fato) --
                # contribui zero pro P&L de qualquer forma, então nem vale
                # gastar uma chamada de histórico na Bloomberg com o ticker
                # dela. Pula antes de validar "Tipo" também, pra não quebrar
                # em linhas de referência com esse campo vazio/preenchido
                # com outra coisa.
                continue
            position_type = str(row[type_col]).strip().lower()
            if position_type not in ("notional", "dv01"):
                raise ValueError(
                    f"{row[asset_col]!r}: Tipo={position_type!r} não reconhecido — use 'Notional' ou 'DV01'."
                )
            positions.append(
                PortfolioPosition(
                    asset=str(row[asset_col]).strip(),
                    ticker=str(ticker).strip(),
                    position_type=position_type,
                    position_value=float(raw_value),
                    asset_class=str(row[class_col]).strip() if class_col else "N/A",
                )
            )
        return positions
