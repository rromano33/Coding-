"""Turns a curve ticker into a maturity date, for the one country where
Bloomberg's MATURITY reference field doesn't do it directly.

Confirmed via inspect_bbg_tickers.py: every country except Brazil exposes
MATURITY straight on the ticker (swaps, NDIRS) — just pull it with
BbgClient.maturities(), no parsing needed. Brazil's DI1 are futures, which
only expose LAST_TRADEABLE_DT (last day you can trade the contract, not
the date the curve pillar belongs on), so its maturity still needs to be
derived from the ticker's futures month code.
"""
from __future__ import annotations

import re
from datetime import date

from emrates.data.calendars import Calendar

_FUTURES_MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
_MONTH_CODE_BY_NUMBER = {month: letter for letter, month in _FUTURES_MONTH_CODES.items()}

_DI1_PATTERN = re.compile(r"^OD([FGHJKMNQUVXZ])(\d{2})\s*Comdty$", re.IGNORECASE)

# Countries whose curve tickers need this module at all; everyone else
# resolves maturity straight from Bloomberg's MATURITY field.
TICKER_STRING_PARSING_COUNTRIES = {"brazil"}


def brazil_di1_maturity(ticker: str, calendar: Calendar) -> date:
    """B3 DI1 futures expire on the first business day of the contract month."""
    match = _DI1_PATTERN.match(ticker.strip())
    if not match:
        raise ValueError(f"ticker {ticker!r} doesn't look like a DI1 future (expected e.g. 'ODQ26 Comdty')")
    month = _FUTURES_MONTH_CODES[match.group(1).upper()]
    year = 2000 + int(match.group(2))
    return calendar.adjust_following(date(year, month, 1))


def brazil_di1_label(maturity: date) -> str:
    """Inverse of brazil_di1_maturity: the DI1 contract code (B3/trading-desk
    style, e.g. 'DIF27') for a pillar that lands on a contract month's first
    business day. Ricardo (29/07/2026) wants this next to each vertex in the
    scenario lab's impact table instead of just the raw maturity date."""
    letter = _MONTH_CODE_BY_NUMBER[maturity.month]
    year_code = maturity.year % 100
    return f"DI{letter}{year_code:02d}"
