"""Roda localmente (Bloomberg Terminal ativo). Diagnóstico detalhado do
pipeline de FRA-strip pra Czech/Poland/Hungary — pra achar exatamente onde
o número final diverge do que a mesa espera (visto comparando contra uma
tabela de referência baseada nos mesmos FRAs).

Mostra, pra cada país:
  1. Cada ticker de FRA cru: período (NxM) e taxa (%) — pra achar se algum
     veio errado/trocado antes de qualquer processamento nosso.
  2. Qual cadeia (best_chain_start) foi escolhida e quais tickers ela usa.
  3. Os pilares e taxas zero da curva já com FRA splicado (antes do NSS).
  4. O caminho de reuniões NA CURVA EXATA (sem NSS) vs NA CURVA COM NSS —
     pra ver se a suavização está inflando/distorcendo o resultado.

Uso:
    python scripts/inspect_fra_strip_detail.py            # roda os 3 países
    python scripts/inspect_fra_strip_detail.py czech       # só um país
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.central_banks.meeting_dates import upcoming_meetings
from emrates.central_banks.stripper import strip_meeting_path
from emrates.curves.base import Pillar
from emrates.curves.factory import build_curve_builder, load_country_config
from emrates.curves.fra_strip import best_chain_start, extend_with_fra_strip, parse_fra_period
from emrates.curves.nss import fit_nss_curve
from emrates.data.bbg_client import BbgClient
from emrates.data.calendars import Calendar, CalendarSet
from emrates.data.excel_loader import InputsBCsLoader

COUNTRIES = ["czech", "poland", "hungary"]


def inspect_country(country, tickers, meetings_by_country, calendars, bbg, valuation_date, settings):
    print(f"\n{'=' * 70}\n{country.upper()}\n{'=' * 70}")

    country_tickers = [t for t in tickers if t.country.strip().lower().replace(" ", "_") == country]
    policy_ticker = next((t for t in country_tickers if t.kind.lower() == "policy"), None)
    all_curve_tickers = [t for t in country_tickers if t.kind.lower() == "curve"]
    fra_tickers = [t for t in all_curve_tickers if "FR" in t.ticker.upper() and "SW" not in t.ticker.upper()]
    curve_tickers = [t for t in all_curve_tickers if "SW" in t.ticker.upper()]

    if policy_ticker is None or not curve_tickers:
        print("sem tickers Policy/Curve — pulei.")
        return

    calendar = calendars.get(country) or Calendar(country, holidays=set())
    cfg = load_country_config(country)
    maturities = bbg.maturities([t.ticker for t in curve_tickers])
    prices = bbg.last_prices([policy_ticker.ticker] + [t.ticker for t in curve_tickers] + [t.ticker for t in fra_tickers])
    current_policy_rate = prices[policy_ticker.ticker] / 100.0
    print(f"policy_rate ({policy_ticker.ticker}) = {current_policy_rate * 100:.3f}%")

    pillars = []
    for t in curve_tickers:
        rate = prices[t.ticker] / 100.0
        if pd.isna(rate):
            continue
        pillars.append(Pillar(maturity=maturities[t.ticker], rate=rate))
    print("\nSwap pillars:")
    for p in sorted(pillars, key=lambda p: p.maturity):
        print(f"  {p.maturity}  {p.rate * 100:.3f}%")
    curve = build_curve_builder(cfg, calendar).build(valuation_date, pillars)

    descriptions = bbg.reference_fields([t.ticker for t in fra_tickers], ["SECURITY_DES", "NAME"])
    fra_data = []
    print("\nRaw FRA tickers:")
    for _, row in descriptions.iterrows():
        period = None
        for field in ("SECURITY_DES", "NAME"):
            try:
                period = parse_fra_period(row[field])
                break
            except ValueError:
                continue
        rate = prices[row["ticker"]] / 100.0
        status = "OK" if period is not None and not pd.isna(rate) else "PULEI"
        print(f"  {row['ticker']:<20} des={row['SECURITY_DES']!r:<20} period={period} rate={rate * 100 if not pd.isna(rate) else 'NaN'}%  [{status}]")
        if period is not None and not pd.isna(rate):
            fra_data.append((*period, rate))

    spot_date = calendar.add_business_days(valuation_date, 2)
    periods = {start: (end, rate) for start, end, rate in fra_data}
    long_anchor_date = curve.pillar_dates[0]
    from emrates.conventions.daycount import DayCount, year_fraction
    long_anchor_month = round(year_fraction(spot_date, long_anchor_date, DayCount.ACT_360, calendar) * 12)
    start, chain = best_chain_start(periods, long_anchor_month)
    print(f"\nlong_anchor_month (1st swap pillar, {long_anchor_date}) = {long_anchor_month}")
    print(f"best_chain_start picked start={start}, chain={chain}")

    extended = extend_with_fra_strip(curve, spot_date, current_policy_rate, fra_data, calendar)
    print(f"\nExtended curve pillars ({len(extended.pillar_dates)} total, was {len(curve.pillar_dates)} swap-only):")
    for d in sorted(extended.pillar_dates):
        tau = (d - valuation_date).days / 365
        print(f"  {d}  zero={extended.zero_rate(d) * 100:.3f}%")

    horizon = settings["reporting"]["meetings_horizon"]
    meetings = upcoming_meetings(meetings_by_country.get(country, []), valuation_date, horizon + 1)
    nss_curve = fit_nss_curve(extended)

    print("\nMeeting path — EXACT (FRA+swap spliced, no NSS) vs NSS-smoothed:")
    for label, c in [("EXACT", extended), ("NSS", nss_curve)]:
        results = strip_meeting_path(c, meetings, current_policy_rate)
        cum = 0.0
        print(f"  {label}:")
        for r in results[:8]:
            cum += 0  # cumulative already tracked by stripper
            print(f"    {r.meeting_date}  Δ={r.implied_change_bps:+7.1f}bps  acumulado={r.cumulative_change_from_spot_bps:+7.1f}bps")


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

    countries = sys.argv[1:] or COUNTRIES
    for country in countries:
        inspect_country(country, tickers, meetings_by_country, calendars, bbg, valuation_date, settings)


if __name__ == "__main__":
    main()
