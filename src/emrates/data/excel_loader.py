"""Reads Input_BCs.xlsx (Tickers / Dates / Posições sheets).

Layout confirmed against the real file via scripts/inspect_inputs.py:

- 'Tickers': columns Ticker, Country, Description, Type (Policy|Curve).
  There is no tenor column — the maturity is implied by the ticker itself
  (e.g. Brazil's DI1 futures encode month+year in the ticker, see
  emrates.data.ticker_parsing). How to turn a given country's curve
  tickers into maturity dates is therefore country-specific code, not a
  config value.

- 'Dates': WIDE format, one column per committee for meeting dates
  (BANXICO, BCCh, Banrep, BCB, SARB, NBP, CNB, MNB) and one column per
  country for holidays (Feriados_<country>), each column an independent,
  ragged list of dates (not row-aligned across columns). The mapping from
  column name to our internal country key lives in
  config/settings.yaml -> dates_columns.meetings / dates_columns.holidays.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class TickerRef:
    country: str
    kind: str  # "Policy" or "Curve"
    description: str
    ticker: str


class InputsBCsLoader:
    def __init__(self, path: str | Path, column_map: dict):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} not found — this loader must run locally where Input_BCs.xlsx lives, "
                "not inside a cloud session"
            )
        self.column_map = column_map

    def load_tickers(self) -> list[TickerRef]:
        cols = self.column_map["tickers"]
        df = pd.read_excel(self.path, sheet_name=self.column_map.get("tickers_sheet", "Tickers"))
        refs = []
        for _, row in df.iterrows():
            refs.append(
                TickerRef(
                    country=str(row[cols["country"]]).strip(),
                    kind=str(row[cols["kind"]]).strip(),
                    description=str(row[cols["description"]]).strip(),
                    ticker=str(row[cols["ticker"]]).strip(),
                )
            )
        return refs

    def _load_wide_date_columns(self, sheet: str, column_to_country: dict[str, str]) -> dict[str, list[date]]:
        df = pd.read_excel(self.path, sheet_name=sheet)
        out: dict[str, list[date]] = {}
        for column, country in column_to_country.items():
            if column not in df.columns:
                continue
            values = pd.to_datetime(df[column].dropna()).dt.date.tolist()
            out[country] = sorted(values)
        return out

    def load_meeting_dates(self) -> dict[str, list[date]]:
        dates_sheet = self.column_map.get("dates_sheet", "Dates")
        return self._load_wide_date_columns(dates_sheet, self.column_map["dates"]["meetings"])

    def load_holidays(self) -> dict[str, list[date]]:
        dates_sheet = self.column_map.get("dates_sheet", "Dates")
        return self._load_wide_date_columns(dates_sheet, self.column_map["dates"]["holidays"])

    def load_positions(self) -> pd.DataFrame:
        """Reads the 'Posições' sheet. Expected columns (see column_map['positions']):
        TradeID, Country, TradeDate, StartDate, MaturityDate, PayReceive, Notional,
        FixedRate, Currency."""
        cols = self.column_map["positions"]
        df = pd.read_excel(self.path, sheet_name=self.column_map.get("positions_sheet", "Posições"))
        return df.rename(columns={v: k for k, v in cols.items()})
