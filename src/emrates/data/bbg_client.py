"""Thin wrapper around xbbg, with a local parquet cache in Data/raw.

Only runs where a Bloomberg Terminal + BBComm is reachable — i.e. locally,
never inside a cloud session. Caching exists so a re-run of the day's
pricing doesn't refire hundreds of BDP/BDH calls against the Terminal.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

try:
    from xbbg import blp
except ImportError:  # allows the rest of the codebase to import/test without xbbg installed
    blp = None


class BbgClient:
    def __init__(self, cache_dir: str | Path = "Data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _require_blp(self):
        if blp is None:
            raise RuntimeError(
                "xbbg is not installed / no Bloomberg Terminal connection available. "
                "This must run locally with a live Terminal session, not in a cloud environment."
            )

    def last_prices(self, tickers: list[str], field: str = "PX_LAST") -> pd.Series:
        self._require_blp()
        df = blp.bdp(tickers=tickers, flds=[field])
        return df[field.upper()]

    def history(
        self,
        tickers: list[str],
        start: date,
        end: date,
        field: str = "PX_LAST",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        cache_file = self.cache_dir / f"history_{field}_{start}_{end}.parquet"
        if use_cache and cache_file.exists():
            cached = pd.read_parquet(cache_file)
            missing = [t for t in tickers if t not in cached.columns]
            if not missing:
                return cached[tickers]

        self._require_blp()
        df = blp.bdh(tickers=tickers, flds=[field], start_date=start, end_date=end)
        df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns

        if use_cache:
            df.to_parquet(cache_file)
        return df
