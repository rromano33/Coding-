"""Roda localmente, DEPOIS de run_daily_pricing.py já ter salvo a curva de
hoje: calcula o PnL do book (carry vs. movimento de curva) comparando com
a última curva salva anterior a hoje.

python scripts/run_pnl.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.data.calendars import CalendarSet
from emrates.data.curve_store import latest_curve_before, load_curve
from emrates.data.excel_loader import InputsBCsLoader
from emrates.portfolio.positions import load_positions
from emrates.reports.pnl_report import pnl_report

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
    calendars = CalendarSet.from_holiday_frame(loader.load_holidays())
    positions = load_positions(loader.load_positions())

    processed_dir = settings["paths"]["processed_dir"]
    valuation_date = date.today()

    curves_t0, curves_t1 = {}, {}
    for country in COUNTRIES:
        today_path = Path(processed_dir) / f"curve_{country}_{valuation_date}.json"
        if not today_path.exists():
            continue
        prior_path = latest_curve_before(processed_dir, country, valuation_date)
        if prior_path is None:
            print(f"[{country}] sem curva anterior salva ainda — pulei (normal no primeiro dia rodando).")
            continue
        curves_t1[country] = load_curve(today_path, calendars[country])
        curves_t0[country] = load_curve(prior_path, calendars[country])

    relevant_positions = [p for p in positions if p.country in curves_t0]
    report = pnl_report(relevant_positions, curves_t0, curves_t1)
    out_path = Path(processed_dir) / f"pnl_{valuation_date}.csv"
    report.to_csv(out_path, index=False)
    print(f"PnL de {len(relevant_positions)} posições -> {out_path}")


if __name__ == "__main__":
    main()
