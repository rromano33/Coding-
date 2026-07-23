"""Thin wrapper around xbbg, with a local parquet cache in Data/raw.

Only runs where a Bloomberg Terminal + BBComm is reachable — i.e. locally,
never inside a cloud session. Caching exists so a re-run of the day's
pricing doesn't refire hundreds of BDP/BDH calls against the Terminal.

Normalizes across xbbg builds: the classic package returns bdp() as a
pandas DataFrame indexed by ticker with one column per field, but at
least one build in the wild (a Rust/narwhals-backed "xbbg-async") returns
a narwhals-wrapped pyarrow Table in LONG format instead — columns
ticker/field/value, one row per (ticker, field) pair. _normalize_bdp
converts either shape into the classic wide/indexed-by-ticker one so the
rest of this module (and its callers) don't need to care which xbbg is
installed.
"""
from __future__ import annotations

import time
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

    def _normalize_bdp(self, raw) -> pd.DataFrame:
        df = raw.to_pandas() if hasattr(raw, "to_pandas") else raw
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        if {"ticker", "field", "value"}.issubset(df.columns):
            wide = df.pivot(index="ticker", columns="field", values="value")
            wide.columns.name = None
            return wide

        if df.index.name != "ticker" and "ticker" in df.columns:
            df = df.set_index("ticker")
        return df

    def _check_bdp_result(self, df: pd.DataFrame, tickers: list[str], fields: list[str]) -> None:
        missing = [f for f in fields if f not in df.columns]
        if len(df) == 0 or missing:
            raise RuntimeError(
                f"BDP não retornou {missing or 'nada'} para {tickers} (colunas recebidas: {list(df.columns)}). "
                "Se isso acontecer de novo depois de uma sessão saudável, é provável que os nomes de campo "
                "estejam errados para esses tickers — confira 'SessionConnectionDown'/'SessionTerminated' no "
                "terminal primeiro para descartar sessão caída."
            )

    def last_prices(self, tickers: list[str], field: str = "PX_LAST") -> pd.Series:
        self._require_blp()
        raw = blp.bdp(tickers=tickers, flds=[field])
        df = self._normalize_bdp(raw)
        self._check_bdp_result(df, tickers, [field])
        return df[field]

    def maturities(self, tickers: list[str]) -> pd.Series:
        """MATURITY reference field, direct from Bloomberg — the right way to resolve
        a curve ticker's maturity for every instrument type that has one (swaps,
        NDIRS, etc). Only Brazil's DI1 futures need ticker-string parsing instead
        (see emrates.data.ticker_parsing.brazil_di1_maturity) since futures expose
        LAST_TRADEABLE_DT, not MATURITY, and that's a different date (last day you
        can trade the contract, not the date the curve pillar should sit on)."""
        self._require_blp()
        raw = blp.bdp(tickers=tickers, flds=["MATURITY"])
        df = self._normalize_bdp(raw)
        self._check_bdp_result(df, tickers, ["MATURITY"])
        return pd.to_datetime(df["MATURITY"]).dt.date

    def reference_fields(self, tickers: list[str], fields: list[str]) -> pd.DataFrame:
        """Pull of arbitrary reference fields, one row per ticker — used to figure out
        how to resolve each ticker's maturity (MATURITY / LAST_TRADEABLE_DT for dated
        instruments, TENOR for generic/constant-maturity curve points) rather than
        parsing it out of the ticker string, which is fragile and country-specific."""
        self._require_blp()
        raw = blp.bdp(tickers=tickers, flds=fields)
        df = self._normalize_bdp(raw)
        if len(df) == 0:
            raise RuntimeError(
                f"BDP não retornou nada para {tickers}. Confira 'SessionConnectionDown'/'SessionTerminated' "
                "no terminal — provavelmente a sessão do Bloomberg Terminal caiu no meio da consulta."
            )
        return df.reset_index().rename(columns={"index": "ticker"})

    def history(
        self,
        tickers: list[str],
        start: date,
        end: date,
        field: str = "PX_LAST",
        use_cache: bool = True,
        batch_size: int = 25,
        retries: int = 2,
        retry_delay_seconds: float = 3.0,
    ) -> pd.DataFrame:
        """Busca histórico diário via BDH, em lotes de `batch_size` tickers,
        com retry por lote.

        Pedir muitos tickers de uma vez (~150+) num único BDH de vários
        meses é pesado o bastante pra derrubar a sessão do Terminal no meio
        da consulta -- xbbg não levanta exceção nesse caso, só devolve um
        DataFrame sem as colunas dos tickers afetados. Em lotes menores,
        uma sessão instável só afeta o lote em andamento, e os outros
        lotes ainda têm chance de completar.

        Mas o mesmo pode acontecer com UM lote pequeno também (sessão do
        BBComm caiu por outro motivo, não tamanho do pedido) -- o log do
        xbbg-async nesse caso avisa 'SessionConnectionDown ... SDK will
        auto-reconnect' antes de eventualmente desistir, então vale
        esperar um pouco e tentar de novo antes de dar esse lote como
        perdido: às vezes o reconnect automático do SDK só precisa de mais
        alguns segundos que a primeira tentativa não deu."""
        cache_file = self.cache_dir / f"history_{field}_{start}_{end}.parquet"
        if use_cache and cache_file.exists():
            cached = pd.read_parquet(cache_file)
            missing = [t for t in tickers if t not in cached.columns]
            if not missing:
                return cached[tickers]

        self._require_blp()

        frames = []
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            batch_df = None
            for attempt in range(retries + 1):
                raw = blp.bdh(tickers=batch, flds=[field], start_date=start, end_date=end)
                candidate = raw.to_pandas() if hasattr(raw, "to_pandas") else raw
                candidate.columns = (
                    candidate.columns.droplevel(1) if isinstance(candidate.columns, pd.MultiIndex) else candidate.columns
                )
                if len(candidate.columns) > 0:
                    batch_df = candidate
                    break
                if attempt < retries:
                    time.sleep(retry_delay_seconds)
            if batch_df is not None:
                frames.append(batch_df)

        if not frames:
            raise RuntimeError(
                f"BDH não retornou histórico para NENHUM dos {len(tickers)} tickers pedidos, mesmo após "
                f"{retries + 1} tentativa(s) por lote. Confira 'SessionConnectionDown'/'SessionTerminated' no "
                "terminal -- a sessão do Bloomberg Terminal (BBComm) provavelmente estava caída ou instável "
                "durante toda a consulta. Verifique se o Terminal está aberto e logado, e tente de novo."
            )

        df = pd.concat(frames, axis=1)

        if use_cache:
            df.to_parquet(cache_file)
        return df
