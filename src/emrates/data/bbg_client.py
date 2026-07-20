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

    def _check_bdp_result(self, df: pd.DataFrame, tickers: list[str], fields: list[str]) -> None:
        missing = [f for f in fields if f.upper() not in df.columns]
        if df.empty or missing:
            raise RuntimeError(
                f"BDP não retornou {missing or 'nada'} para {tickers} (colunas recebidas: {list(df.columns)}). "
                "Isso normalmente é sessão do Bloomberg Terminal caída no meio da consulta, não bug de código — "
                "procure 'SessionConnectionDown' / 'SessionTerminated' no terminal, confirme que o Terminal "
                "está logado e tente de novo."
            )

    def last_prices(self, tickers: list[str], field: str = "PX_LAST") -> pd.Series:
        self._require_blp()
        df = blp.bdp(tickers=tickers, flds=[field])
        self._check_bdp_result(df, tickers, [field])
        return df[field.upper()]

    def reference_fields(self, tickers: list[str], fields: list[str]) -> pd.DataFrame:
        """Raw BDP pull of arbitrary reference fields — used to figure out how to
        resolve each ticker's maturity (MATURITY / LAST_TRADEABLE_DT for dated
        instruments, TENOR for generic/constant-maturity curve points) rather than
        parsing it out of the ticker string, which is fragile and country-specific."""
        self._require_blp()
        df = blp.bdp(tickers=tickers, flds=fields)
        if df.empty:
            raise RuntimeError(
                f"BDP não retornou nada para {tickers}. Provavelmente sessão do Bloomberg Terminal caída "
                "no meio da consulta — procure 'SessionConnectionDown' / 'SessionTerminated' no terminal, "
                "confirme que o Terminal está logado e tente de novo."
            )
        return df

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
