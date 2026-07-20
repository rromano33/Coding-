"""Reads Inputs_BCs.xlsx (Tickers / Dates / Posições sheets).

The exact column names below are a best guess from the description given
("aba Tickers com Policy/curve por país", "aba Dates com reuniões e
feriados") and have NOT been validated against the real file yet — run
scripts/inspect_inputs.py locally and adjust the `*_columns` mappings in
config/settings.yaml to match what it prints before trusting this module.
Everything here reads through that mapping rather than hardcoding column
names, so fixing settings.yaml should be enough — no code changes.
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
    tenor: str | None
    ticker: str


class InputsBCsLoader:
    def __init__(self, path: str | Path, column_map: dict):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} not found — this loader must run locally where Inputs_BCs.xlsx lives, "
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
                    tenor=(None if pd.isna(row.get(cols.get("tenor", ""))) else str(row[cols["tenor"]]).strip()),
                    ticker=str(row[cols["ticker"]]).strip(),
                )
            )
        return refs

    def load_meeting_dates(self) -> dict[str, list[date]]:
        cols = self.column_map["dates"]
        df = pd.read_excel(self.path, sheet_name=self.column_map.get("dates_sheet", "Dates"))
        meetings = df[df[cols["event_type"]].str.lower() == "meeting"]
        out: dict[str, list[date]] = {}
        for country, group in meetings.groupby(cols["country"]):
            out[str(country).strip()] = sorted(pd.to_datetime(group[cols["date"]]).dt.date.tolist())
        return out

    def load_holidays(self) -> dict[str, list[date]]:
        cols = self.column_map["dates"]
        df = pd.read_excel(self.path, sheet_name=self.column_map.get("dates_sheet", "Dates"))
        holidays = df[df[cols["event_type"]].str.lower() == "holiday"]
        out: dict[str, list[date]] = {}
        for country, group in holidays.groupby(cols["country"]):
            out[str(country).strip()] = sorted(pd.to_datetime(group[cols["date"]]).dt.date.tolist())
        return out

    def load_positions(self) -> pd.DataFrame:
        """Reads the 'Posições' sheet — layout proposed in README.md, add it to
        Inputs_BCs.xlsx before calling this. Expected columns (see column_map['positions']):
        TradeID, Country, TradeDate, StartDate, MaturityDate, PayReceive, Notional,
        FixedRate, Currency."""
        cols = self.column_map["positions"]
        df = pd.read_excel(self.path, sheet_name=self.column_map.get("positions_sheet", "Posições"))
        return df.rename(columns={v: k for k, v in cols.items()})
