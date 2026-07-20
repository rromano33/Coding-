"""Rate <-> discount factor conversions per compounding style.

EXPONENTIAL is the Brazilian convention: DF = (1 + r) ** -tau, tau in
BUS/252 years. LINEAR is the simple-interest convention used for
short-stub money-market-style quoting: DF = 1 / (1 + r * tau).
COMPOUNDED_DAILY represents an OIS-style rate that already reflects
daily compounding of an overnight index over the period (Cámara, IBR,
JIBAR-OIS-equivalent): treated the same as EXPONENTIAL for discounting
purposes once expressed as an annualized rate over tau, since a bullet
OIS swap's par rate *is* the compounded zero rate for that tenor.
"""
from __future__ import annotations

from enum import Enum


class Compounding(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    COMPOUNDED_DAILY = "compounded_daily"


def discount_factor(rate: float, tau: float, compounding: Compounding) -> float:
    if compounding in (Compounding.EXPONENTIAL, Compounding.COMPOUNDED_DAILY):
        return (1.0 + rate) ** (-tau)
    if compounding == Compounding.LINEAR:
        return 1.0 / (1.0 + rate * tau)
    raise ValueError(f"unknown compounding: {compounding}")


def zero_rate(df: float, tau: float, compounding: Compounding) -> float:
    if tau <= 0:
        raise ValueError("tau must be positive to back out a zero rate")
    if compounding in (Compounding.EXPONENTIAL, Compounding.COMPOUNDED_DAILY):
        return df ** (-1.0 / tau) - 1.0
    if compounding == Compounding.LINEAR:
        return (1.0 / df - 1.0) / tau
    raise ValueError(f"unknown compounding: {compounding}")


def forward_rate(df_start: float, df_end: float, tau: float, compounding: Compounding) -> float:
    """Annualized forward rate implied between two discount factors, tau apart (in years)."""
    if tau <= 0:
        raise ValueError("tau must be positive to back out a forward rate")
    ratio = df_start / df_end
    if compounding in (Compounding.EXPONENTIAL, Compounding.COMPOUNDED_DAILY):
        return ratio ** (1.0 / tau) - 1.0
    if compounding == Compounding.LINEAR:
        return (ratio - 1.0) / tau
    raise ValueError(f"unknown compounding: {compounding}")
