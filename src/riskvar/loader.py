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


class PortfolioLoader:
    def __init__(self, path: str | Path, sheet: str, column_map: dict):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} não encontrado — rode isso localmente, onde a planilha do portfólio está."
            )
        self.sheet = sheet
        self.column_map = column_map

    def load(self) -> list[PortfolioPosition]:
        df = pd.read_excel(self.path, sheet_name=self.sheet)
        cols = self.column_map
        positions = []
        for _, row in df.iterrows():
            ticker = row[cols["ticker"]]
            if pd.isna(ticker):
                continue
            position_type = str(row[cols["position_type"]]).strip().lower()
            if position_type not in ("notional", "dv01"):
                raise ValueError(
                    f"{row[cols['asset']]!r}: Tipo={position_type!r} não reconhecido — use 'Notional' ou 'DV01'."
                )
            positions.append(
                PortfolioPosition(
                    asset=str(row[cols["asset"]]).strip(),
                    ticker=str(ticker).strip(),
                    position_type=position_type,
                    position_value=float(row[cols["position_value"]]),
                )
            )
        return positions
