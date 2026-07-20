"""Roda localmente (Bloomberg Terminal ativo). Para cada uma das próximas N
reuniões do Copom, mostra os dois vencimentos de DI1 usados para
interpolar aquela data (bracket), suas taxas, e o nível resultante —
para comparar ponto a ponto com a tela CDIE da Bloomberg e achar
exatamente onde a curva diverge.

Usage: python scripts/inspect_stripper_brazil.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.central_banks.meeting_dates import upcoming_meetings
from emrates.curves.base import Pillar, ZeroRateCurveBuilder
from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.data.bbg_client import BbgClient
from emrates.data.calendars import Calendar, CalendarSet
from emrates.data.excel_loader import InputsBCsLoader
from emrates.data.ticker_parsing import brazil_di1_maturity


def bracket(pillar_dates: list[date], d: date) -> tuple[date, date]:
    if d <= pillar_dates[0]:
        return pillar_dates[0], pillar_dates[0]
    if d >= pillar_dates[-1]:
        return pillar_dates[-2], pillar_dates[-1]
    for k in range(len(pillar_dates) - 1):
        if pillar_dates[k] <= d <= pillar_dates[k + 1]:
            return pillar_dates[k], pillar_dates[k + 1]
    return pillar_dates[-2], pillar_dates[-1]


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
    calendar = calendars.get("brazil") or Calendar("brazil", holidays=set())

    brazil_curve = [
        t for t in tickers if t.country.strip().lower().replace(" ", "_") == "brazil" and t.kind.lower() == "curve"
    ]
    policy_ticker = next(
        t for t in tickers if t.country.strip().lower().replace(" ", "_") == "brazil" and t.kind.lower() == "policy"
    )

    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    prices = bbg.last_prices([policy_ticker.ticker] + [t.ticker for t in brazil_curve])
    current_policy_rate = prices[policy_ticker.ticker] / 100.0

    pillars = sorted(
        [Pillar(maturity=brazil_di1_maturity(t.ticker, calendar), rate=prices[t.ticker] / 100.0) for t in brazil_curve],
        key=lambda p: p.maturity,
    )
    curve = ZeroRateCurveBuilder(DayCount.BUS_252, Compounding.EXPONENTIAL, calendar).build(date.today(), pillars)

    valuation_date = date.today()
    horizon = settings["reporting"]["meetings_horizon"]
    meetings = upcoming_meetings(meetings_by_country.get("brazil", []), valuation_date, horizon + 1)
    boundary_dates = [valuation_date] + meetings

    pillar_dates = [p.maturity for p in pillars]
    rate_by_date = {p.maturity: p.rate for p in pillars}

    print(f"valuation_date={valuation_date}  BZDIOVRA={current_policy_rate*100:.3f}\n")
    for i in range(len(boundary_dates) - 1):
        d = boundary_dates[i + 1]
        t0, t1 = bracket(pillar_dates, d)
        level = curve.forward_rate(boundary_dates[i], d) * 1e4
        print(
            f"{d}  bracket=({t0} @ {rate_by_date.get(t0, current_policy_rate)*100:.3f}%, "
            f"{t1} @ {rate_by_date.get(t1, current_policy_rate)*100:.3f}%)  "
            f"level_bps={level:.1f}"
        )


if __name__ == "__main__":
    main()
