"""Formats the book_risk() output into the daily PnL report."""
from __future__ import annotations

import pandas as pd

from emrates.curves.base import DiscountCurve
from emrates.portfolio.risk import book_risk
from emrates.pricing.instruments import Swap


def pnl_report(positions: list[Swap], curves_t0: dict[str, DiscountCurve], curves_t1: dict[str, DiscountCurve]) -> pd.DataFrame:
    df = book_risk(positions, curves_t0, curves_t1)
    totals = df[["dv01", "pnl_total", "pnl_carry", "pnl_curve_move"]].sum()
    totals["trade_id"] = "TOTAL"
    totals["country"] = ""
    return pd.concat([df, totals.to_frame().T], ignore_index=True)
