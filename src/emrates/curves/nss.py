"""Nelson-Siegel-Svensson curve fit — a smoothed curve for the priced_bc
report specifically.

Any interpolation that reproduces every single DI1/swap pillar exactly
(log-linear, monotone cubic, whatever) inherits the real, small pillar-to-
pillar zigzag in traded market prices — and extracting a meeting-dated
forward rate over a short window far from the valuation date amplifies
that zigzag by roughly t_start/(t_end-t_start), turning a few bps of
market microstructure noise into tens of bps of spurious "priced" moves.
That's confirmed against Bloomberg's own CDIE screen, which shows this
exact effect on its raw "Last" column but not on its smoothed "Est" one.

NSS fits a smooth 6-parameter curve by least squares instead of exact
interpolation — it does NOT reproduce every pillar exactly, by design;
that's what removes the noise. This is why it's used only for the
priced_bc report (a read on the market's aggregate policy-path view),
never for pricing/PnL of actual positions, where marking against what the
market exactly trades at is the correct behavior.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from emrates.conventions.daycount import DayCount, year_fraction
from emrates.data.calendars import Calendar


@dataclass(frozen=True)
class NssParams:
    beta0: float
    beta1: float
    beta2: float
    beta3: float
    tau1: float
    tau2: float


def nss_zero_rate(t: float, p: NssParams) -> float:
    """Continuously-compounded zero rate at maturity t (years)."""
    if t <= 0:
        return p.beta0 + p.beta1
    x1 = t / p.tau1
    decay1 = (1 - math.exp(-x1)) / x1
    x2 = t / p.tau2
    decay2 = (1 - math.exp(-x2)) / x2
    return p.beta0 + p.beta1 * decay1 + p.beta2 * (decay1 - math.exp(-x1)) + p.beta3 * (decay2 - math.exp(-x2))


def fit_nss(t_values: list[float], zero_rates_cc: list[float]) -> NssParams:
    from scipy.optimize import least_squares

    def residuals(x):
        p = NssParams(*x)
        return [nss_zero_rate(t, p) - z for t, z in zip(t_values, zero_rates_cc)]

    long_end = zero_rates_cc[-1]
    short_end = zero_rates_cc[0]
    x0 = [long_end, short_end - long_end, 0.0, 0.0, 1.0, 3.0]
    bounds = ([-1.0, -1.0, -1.0, -1.0, 0.05, 0.05], [1.0, 1.0, 1.0, 1.0, 30.0, 30.0])
    result = least_squares(residuals, x0, bounds=bounds)
    return NssParams(*result.x)


class NssCurve:
    """Drop-in replacement for DiscountCurve's forward_rate()/valuation_date,
    sufficient for central_banks/stripper.py — not meant for swap valuation."""

    def __init__(self, valuation_date: date, convention: DayCount, calendar: Calendar | None, params: NssParams):
        self.valuation_date = valuation_date
        self.convention = convention
        self.calendar = calendar
        self.params = params

    def tau(self, start: date, end: date) -> float:
        return year_fraction(start, end, self.convention, self.calendar)

    def discount_factor(self, d: date) -> float:
        if d == self.valuation_date:
            return 1.0
        t = self.tau(self.valuation_date, d)
        return math.exp(-nss_zero_rate(t, self.params) * t)

    def forward_rate(self, start: date, end: date) -> float:
        tau = self.tau(start, end)
        df_start, df_end = self.discount_factor(start), self.discount_factor(end)
        return (df_start / df_end) ** (1.0 / tau) - 1.0


def fit_nss_curve(curve) -> NssCurve:
    """Fits an NssCurve to an existing (exact) DiscountCurve's own pillars."""
    t_values, zero_rates_cc, bad = [], [], []
    for d, df in zip(curve.pillar_dates, curve.discount_factors):
        t = curve.tau(curve.valuation_date, d)
        if t <= 0 or df is None or not math.isfinite(df) or df <= 0:
            bad.append((d, df, t))
            continue
        t_values.append(t)
        zero_rates_cc.append(-math.log(df) / t)

    if bad:
        raise ValueError(
            "fit_nss_curve: pilar(es) inválido(s) (data, discount_factor, tau) antes de ajustar a curva: "
            f"{bad} — confira se o preço/vencimento desses tickers veio correto da Bloomberg."
        )

    params = fit_nss(t_values, zero_rates_cc)
    return NssCurve(curve.valuation_date, curve.convention, curve.calendar, params)
