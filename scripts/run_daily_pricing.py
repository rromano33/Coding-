"""Roda localmente (Bloomberg Terminal ativo): para cada país, monta a curva
do dia a partir dos tickers da Input_BCs.xlsx e gera o relatório de
'quanto está precificado' por reunião do Banco Central.

python scripts/run_daily_pricing.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.central_banks.meeting_dates import upcoming_meetings
from emrates.curves.base import Pillar
from emrates.curves.factory import build_curve_builder, load_country_config
from emrates.data.bbg_client import BbgClient
from emrates.data.calendars import CalendarSet
from emrates.data.excel_loader import InputsBCsLoader
from emrates.conventions.schedule import tenor_to_date
from emrates.data.curve_store import save_curve
from emrates.reports.priced_bc import priced_bc_report

COUNTRIES = ["brazil", "mexico", "chile", "colombia", "south_africa", "poland", "czech", "hungary"]


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
    meetings_by_country = loader.load_meeting_dates()
    calendars = CalendarSet.from_holiday_frame(loader.load_holidays())
    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    valuation_date = date.today()

    Path(settings["paths"]["processed_dir"]).mkdir(parents=True, exist_ok=True)

    for country in COUNTRIES:
        cfg = load_country_config(country)
        calendar = calendars[country]
        country_tickers = [t for t in tickers if t.country.strip().lower() == country]
        policy_ticker = next((t for t in country_tickers if t.kind.lower() == "policy"), None)
        curve_tickers = [t for t in country_tickers if t.kind.lower() == "curve"]
        if policy_ticker is None or not curve_tickers:
            print(f"[{country}] sem tickers Policy/Curve na planilha — pulei. Confirme a aba Tickers.")
            continue

        prices = bbg.last_prices([policy_ticker.ticker] + [t.ticker for t in curve_tickers])
        current_policy_rate = prices[policy_ticker.ticker] / 100.0

        pillars = [
            Pillar(maturity=tenor_to_date(valuation_date, t.tenor), rate=prices[t.ticker] / 100.0)
            for t in curve_tickers
        ]
        curve = build_curve_builder(cfg, calendar).build(valuation_date, pillars)
        save_curve(curve, settings["paths"]["processed_dir"], country)

        meetings = upcoming_meetings(meetings_by_country.get(country, []), valuation_date)
        report = priced_bc_report(curve, meetings, current_policy_rate)
        out_path = Path(settings["paths"]["processed_dir"]) / f"priced_bc_{country}_{valuation_date}.csv"
        report.to_csv(out_path, index=False)
        print(f"[{country}] {len(report)} reuniões precificadas -> {out_path}")


if __name__ == "__main__":
    main()
