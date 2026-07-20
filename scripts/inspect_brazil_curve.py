"""Roda localmente (Bloomberg Terminal ativo). Lista, em ordem de
vencimento, todo ticker de curva do Brasil junto com o preço puxado via
BDP — para comparar linha a linha com a coluna 'Last' da tela CDIE da
Bloomberg e achar tickers/preços fora do lugar.

Usage: python scripts/inspect_brazil_curve.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.data.bbg_client import BbgClient
from emrates.data.calendars import Calendar, CalendarSet
from emrates.data.excel_loader import InputsBCsLoader
from emrates.data.ticker_parsing import brazil_di1_maturity


def main() -> None:
    settings = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))
    column_map = {
        "tickers": settings["tickers_columns"],
        "tickers_sheet": settings["sheets"]["tickers_sheet"],
        "dates": settings["dates_columns"],
        "dates_sheet": settings["sheets"]["dates_sheet"],
        "positions": settings["positions_columns"],
        "positions_sheet": settings["sheets"]["positions_sheet"],
    }
    loader = InputsBCsLoader(settings["paths"]["inputs_bcs"], column_map)
    tickers = loader.load_tickers()
    calendars = CalendarSet.from_holiday_frame(loader.load_holidays())
    calendar = calendars.get("brazil") or Calendar("brazil", holidays=set())

    brazil_curve = [
        t for t in tickers if t.country.strip().lower().replace(" ", "_") == "brazil" and t.kind.lower() == "curve"
    ]
    print(f"{len(brazil_curve)} tickers de curva do Brasil na aba Tickers\n")

    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    prices = bbg.last_prices([t.ticker for t in brazil_curve])

    rows = []
    for t in brazil_curve:
        try:
            maturity = brazil_di1_maturity(t.ticker, calendar)
        except ValueError as exc:
            print(f"ERRO ao interpretar vencimento de {t.ticker!r}: {exc}")
            continue
        rows.append((maturity, t.ticker, t.description, prices[t.ticker]))

    rows.sort(key=lambda r: r[0])
    print(f"{'maturity':<12} {'ticker':<16} {'description':<28} price")
    for maturity, ticker, description, price in rows:
        print(f"{str(maturity):<12} {ticker:<16} {description:<28} {price}")


if __name__ == "__main__":
    main()
