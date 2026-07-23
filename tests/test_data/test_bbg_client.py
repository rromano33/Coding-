from datetime import date

import pandas as pd
import pytest

import emrates.data.bbg_client as bbg_client_module
from emrates.data.bbg_client import BbgClient


def _bdh_df(tickers: list[str], dates: list[date]) -> pd.DataFrame:
    columns = pd.MultiIndex.from_product([tickers, ["PX_LAST"]])
    data = {(t, "PX_LAST"): [100.0 + i for i in range(len(dates))] for t in tickers}
    return pd.DataFrame(data, index=pd.to_datetime(dates), columns=columns)


class _FakeBlp:
    """Simula xbbg.blp: cada lote pedido em .bdh() volta cheio (dataframe
    normal), vazio pra sempre (`dead_batches`, sessão caída sem recuperar),
    ou vazio só nas primeiras N tentativas e depois se recupera
    (`flaky_batches`, simulando o auto-reconnect do SDK)."""

    def __init__(
        self,
        dead_batches: set[frozenset] | None = None,
        flaky_batches: dict[frozenset, int] | None = None,
    ):
        self.dead_batches = dead_batches or set()
        self.flaky_batches = dict(flaky_batches or {})
        self.calls: list[list[str]] = []

    def bdh(self, tickers, flds, start_date, end_date):
        self.calls.append(list(tickers))
        key = frozenset(tickers)
        if key in self.dead_batches:
            return pd.DataFrame()
        if self.flaky_batches.get(key, 0) > 0:
            self.flaky_batches[key] -= 1
            return pd.DataFrame()
        return _bdh_df(tickers, [date(2026, 1, 1), date(2026, 1, 2)])


def test_history_splits_requests_into_batches(tmp_path, monkeypatch):
    fake = _FakeBlp()
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)
    tickers = [f"T{i}" for i in range(55)]

    df = client.history(tickers, date(2026, 1, 1), date(2026, 1, 2), batch_size=25, use_cache=False)

    assert [len(c) for c in fake.calls] == [25, 25, 5]
    assert sorted(df.columns) == sorted(tickers)


def test_history_survives_a_dead_batch_by_keeping_the_others(tmp_path, monkeypatch):
    tickers = [f"T{i}" for i in range(30)]  # 2 lotes de 15
    dead_batch = frozenset(tickers[15:30])
    fake = _FakeBlp(dead_batches={dead_batch})
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)

    df = client.history(
        tickers, date(2026, 1, 1), date(2026, 1, 2), batch_size=15, use_cache=False, retry_delay_seconds=0
    )

    assert sorted(df.columns) == sorted(tickers[:15])
    for missing_ticker in tickers[15:30]:
        assert missing_ticker not in df.columns


def test_history_raises_clear_error_when_every_batch_comes_back_empty(tmp_path, monkeypatch):
    tickers = [f"T{i}" for i in range(10)]
    fake = _FakeBlp(dead_batches={frozenset(tickers)})
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)

    with pytest.raises(RuntimeError, match="SessionConnectionDown"):
        client.history(
            tickers, date(2026, 1, 1), date(2026, 1, 2), batch_size=25, use_cache=False, retry_delay_seconds=0
        )


def test_history_retries_a_batch_that_recovers_after_a_transient_drop(tmp_path, monkeypatch):
    # Simula o log real do xbbg-async: 'SessionConnectionDown ... SDK will
    # auto-reconnect' -- a primeira tentativa falha, a segunda (depois do
    # reconnect) funciona.
    tickers = ["A", "B"]
    fake = _FakeBlp(flaky_batches={frozenset(tickers): 1})
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)

    df = client.history(
        tickers, date(2026, 1, 1), date(2026, 1, 2), retries=2, retry_delay_seconds=0, use_cache=False
    )

    assert sorted(df.columns) == tickers
    assert len(fake.calls) == 2  # 1a tentativa falhou, 2a teve sucesso -- não precisou de uma 3a


def test_history_gives_up_a_batch_after_exhausting_retries(tmp_path, monkeypatch):
    tickers = ["A", "B"]
    fake = _FakeBlp(dead_batches={frozenset(tickers)})
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)

    with pytest.raises(RuntimeError):
        client.history(
            tickers, date(2026, 1, 1), date(2026, 1, 2), retries=2, retry_delay_seconds=0, use_cache=False
        )

    assert len(fake.calls) == 3  # tentativa inicial + 2 retries


def test_history_uses_cache_when_all_tickers_already_present(tmp_path, monkeypatch):
    fake = _FakeBlp()
    monkeypatch.setattr(bbg_client_module, "blp", fake)
    client = BbgClient(cache_dir=tmp_path)
    tickers = ["A", "B"]

    client.history(tickers, date(2026, 1, 1), date(2026, 1, 2), use_cache=True)
    assert len(fake.calls) == 1

    client.history(tickers, date(2026, 1, 1), date(2026, 1, 2), use_cache=True)
    assert len(fake.calls) == 1  # segunda chamada veio do cache, não bateu no fake blp de novo
