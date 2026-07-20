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
from emrates.curves.fra_strip import extend_with_fra_strip, parse_fra_period
from emrates.data.bbg_client import BbgClient
from emrates.data.calendars import Calendar, CalendarSet
from emrates.data.excel_loader import InputsBCsLoader
from emrates.data.ticker_parsing import TICKER_STRING_PARSING_COUNTRIES, brazil_di1_maturity
from emrates.data.curve_store import save_curve
from emrates.curves.nss import fit_nss_curve
from emrates.reports.priced_bc import priced_bc_report

COUNTRIES = ["brazil", "mexico", "chile", "colombia", "south_africa", "poland", "czech", "hungary"]

# Czech/Poland/Hungary's Tickers rows mix FRA tickers (xxFR..., short end,
# handled separately via fra_strip.py) with swap tickers (xxSW..., 1Y+).
FRA_STRIP_COUNTRIES = {"czech", "poland", "hungary"}


def resolve_maturities(bbg: BbgClient, country: str, curve_tickers: list, calendar) -> list:
    if country in TICKER_STRING_PARSING_COUNTRIES:
        return [brazil_di1_maturity(t.ticker, calendar) for t in curve_tickers]
    maturities = bbg.maturities([t.ticker for t in curve_tickers])
    return [maturities[t.ticker] for t in curve_tickers]


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
        # Country names in the sheet aren't confirmed to match our config keys
        # 1:1 yet (only "Brazil" -> "brazil" is verified) — best-effort match
        # for now via lowercase + underscore.
        country_tickers = [t for t in tickers if t.country.strip().lower().replace(" ", "_") == country]
        policy_ticker = next((t for t in country_tickers if t.kind.lower() == "policy"), None)
        all_curve_tickers = [t for t in country_tickers if t.kind.lower() == "curve"]

        fra_tickers = []
        curve_tickers = all_curve_tickers
        if country in FRA_STRIP_COUNTRIES:
            fra_tickers = [t for t in all_curve_tickers if "FR" in t.ticker.upper() and "SW" not in t.ticker.upper()]
            curve_tickers = [t for t in all_curve_tickers if "SW" in t.ticker.upper()]

        if policy_ticker is None or not curve_tickers:
            print(f"[{country}] sem tickers Policy/Curve na planilha (ou nome do país não bate) — pulei.")
            continue

        calendar = calendars.get(country) or Calendar(country, holidays=set())
        if calendars.get(country) is None:
            print(f"[{country}] sem coluna de feriados na aba Dates — usando calendário vazio (dias úteis = seg-sex).")

        pillars_maturities = resolve_maturities(bbg, country, curve_tickers, calendar)

        cfg = load_country_config(country)
        prices = bbg.last_prices([policy_ticker.ticker] + [t.ticker for t in curve_tickers] + [t.ticker for t in fra_tickers])
        current_policy_rate = prices[policy_ticker.ticker] / 100.0

        pillars = [
            Pillar(maturity=maturity, rate=prices[t.ticker] / 100.0)
            for t, maturity in zip(curve_tickers, pillars_maturities)
        ]
        curve = build_curve_builder(cfg, calendar).build(valuation_date, pillars)

        if fra_tickers:
            descriptions = bbg.reference_fields([t.ticker for t in fra_tickers], ["SECURITY_DES"])
            fra_data = []
            for _, row in descriptions.iterrows():
                try:
                    period = parse_fra_period(row["SECURITY_DES"])
                except ValueError as exc:
                    print(f"[{country}] pulei {row['ticker']}: {exc}")
                    continue
                fra_data.append((*period, prices[row["ticker"]] / 100.0))
            spot_date = calendar.add_business_days(valuation_date, 2)
            curve = extend_with_fra_strip(curve, spot_date, current_policy_rate, fra_data, calendar)

        save_curve(curve, settings["paths"]["processed_dir"], country)

        # +1: strip_meeting_path needs one meeting past the horizon to read the
        # priced change *at* the last meeting you actually care about (see
        # central_banks/stripper.py's docstring).
        horizon = settings["reporting"]["meetings_horizon"]
        meetings = upcoming_meetings(meetings_by_country.get(country, []), valuation_date, horizon + 1)
        # Smoothed (NSS) curve for this report only — meeting-dated forwards over
        # short windows far from today amplify the exact curve's pillar-to-pillar
        # market noise into spurious swings (see curves/nss.py docstring). Position
        # valuation/PnL keeps using the exact `curve`, saved above.
        smoothed_curve = fit_nss_curve(curve)
        report = priced_bc_report(smoothed_curve, meetings, current_policy_rate)
        out_path = Path(settings["paths"]["processed_dir"]) / f"priced_bc_{country}_{valuation_date}.csv"
        report.to_csv(out_path, index=False)
        print(f"[{country}] {len(report)} reuniões precificadas -> {out_path}")


if __name__ == "__main__":
    main()
