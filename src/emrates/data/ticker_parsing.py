"""Turns a country's curve ticker into a maturity date.

There's no tenor column in the real Tickers sheet — the maturity is
encoded in the ticker itself, and how it's encoded is specific to each
country's curve instrument (futures month codes, swap tenor suffixes,
etc.), so this can't be config-driven like the day-count/compounding
conventions are.

Only Brazil is implemented so far, confirmed against real tickers
(ODQ26 Comdty, ODU26 Comdty, ...). The other seven countries need a
sample of their actual Tickers-sheet rows before this can be written
correctly — guessing the format would silently mis-price the curve.
"""
from __future__ import annotations

import re
from datetime import date

from emrates.data.calendars import Calendar

_FUTURES_MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

_DI1_PATTERN = re.compile(r"^OD([FGHJKMNQUVXZ])(\d{2})\s*Comdty$", re.IGNORECASE)


def brazil_di1_maturity(ticker: str, calendar: Calendar) -> date:
    """B3 DI1 futures expire on the first business day of the contract month."""
    match = _DI1_PATTERN.match(ticker.strip())
    if not match:
        raise ValueError(f"ticker {ticker!r} doesn't look like a DI1 future (expected e.g. 'ODQ26 Comdty')")
    month = _FUTURES_MONTH_CODES[match.group(1).upper()]
    year = 2000 + int(match.group(2))
    return calendar.adjust_following(date(year, month, 1))


def _not_implemented(country: str):
    def _raise(ticker: str, calendar: Calendar) -> date:
        raise NotImplementedError(
            f"no maturity parser for {country!r} curve tickers yet — need real sample tickers from "
            "the Tickers sheet (run inspect_inputs.py filtered to this country) before this can be written"
        )
    return _raise


MATURITY_PARSERS = {
    "brazil": brazil_di1_maturity,
    "mexico": _not_implemented("mexico"),
    "chile": _not_implemented("chile"),
    "colombia": _not_implemented("colombia"),
    "south_africa": _not_implemented("south_africa"),
    "poland": _not_implemented("poland"),
    "czech": _not_implemented("czech"),
    "hungary": _not_implemented("hungary"),
}
