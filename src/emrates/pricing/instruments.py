"""Position representation for a single swap trade."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class PayReceive(str, Enum):
    PAY = "pay"       # pays fixed, receives floating ("tomado" em taxa, na fala da mesa)
    RECEIVE = "receive"  # receives fixed, pays floating ("aplicado" em taxa)


@dataclass(frozen=True)
class Swap:
    trade_id: str
    country: str
    start_date: date
    maturity_date: date
    fixed_rate: float
    notional: float
    pay_receive: PayReceive
    coupon_frequency_months: int | None = None  # None => bullet/zero-style (Brazil DI, Chile Cámara, Colombia IBR)
