"""Loads the book of open swap positions from the 'Posições' sheet."""
from __future__ import annotations

import pandas as pd

from emrates.pricing.instruments import PayReceive, Swap

COUPON_FREQUENCY_BY_COUNTRY = {
    # None => bullet/zero-style (no interim coupon). Confirm against config/countries/*.yaml
    # before relying on this for anything but Brazil/Chile/Colombia, which the research pass
    # confirmed. The others are the research pass's best guess (6M for JIBAR/WIBOR/PRIBOR/BUBOR,
    # 28-day equivalent for TIIE de Fondeo) — VERIFICAR on the Terminal.
    "brazil": None,
    "chile": None,
    "colombia": None,
    "mexico": 1,  # ~28-day periods approximated as monthly; refine once TIIE de Fondeo schedule is confirmed
    "south_africa": 3,
    "poland": 6,
    "czech": 6,
    "hungary": 6,
}


def load_positions(df: pd.DataFrame) -> list[Swap]:
    swaps = []
    for _, row in df.iterrows():
        country = str(row["Country"]).strip().lower()
        swaps.append(
            Swap(
                trade_id=str(row["TradeID"]),
                country=country,
                start_date=pd.Timestamp(row["StartDate"]).date(),
                maturity_date=pd.Timestamp(row["MaturityDate"]).date(),
                fixed_rate=float(row["FixedRate"]),
                notional=float(row["Notional"]),
                pay_receive=PayReceive(str(row["PayReceive"]).strip().lower()),
                coupon_frequency_months=COUPON_FREQUENCY_BY_COUNTRY.get(country),
            )
        )
    return swaps
