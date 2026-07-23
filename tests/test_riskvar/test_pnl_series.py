from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.loader import PortfolioPosition
from riskvar.pnl_series import portfolio_pnl_series, position_pnl_series


def _series(values: list[float]) -> pd.Series:
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=pd.to_datetime(dates))


def test_notional_position_pnl_is_position_value_times_pct_return():
    position = PortfolioPosition(asset="Ação X", ticker="X", position_type="notional", position_value=1_000_000)
    prices = _series([100.0, 102.0, 101.0])
    pnl = position_pnl_series(position, prices)
    assert pnl.iloc[0] == pytest.approx(1_000_000 * (102.0 / 100.0 - 1))
    assert pnl.iloc[1] == pytest.approx(1_000_000 * (101.0 / 102.0 - 1))


def test_dv01_position_pnl_is_dv01_times_bps_change_on_a_1bp_up_convention():
    # DV01 positivo = ganha quando a taxa SOBE (mesma convenção de
    # emrates.portfolio.risk.dv01: NPV para bump de +1bp).
    position = PortfolioPosition(asset="Swap Y", ticker="Y", position_type="dv01", position_value=5_000)
    yields_pct = _series([10.00, 10.05, 9.95])  # +5bps depois -10bps
    pnl = position_pnl_series(position, yields_pct)
    assert pnl.iloc[0] == pytest.approx(5_000 * 5.0)
    assert pnl.iloc[1] == pytest.approx(5_000 * -10.0)


def test_portfolio_pnl_sums_across_positions_aligned_by_date():
    notional = PortfolioPosition(asset="Ação X", ticker="X", position_type="notional", position_value=1_000_000)
    dv01_pos = PortfolioPosition(asset="Swap Y", ticker="Y", position_type="dv01", position_value=5_000)
    prices = {
        "X": _series([100.0, 102.0]),
        "Y": _series([10.00, 10.05]),
    }
    pnl = portfolio_pnl_series([notional, dv01_pos], prices)
    assert len(pnl) == 1
    expected = 1_000_000 * (102.0 / 100.0 - 1) + 5_000 * 5.0
    assert pnl.iloc[0] == pytest.approx(expected)


def test_portfolio_pnl_treats_missing_quote_day_as_zero_for_that_position():
    notional = PortfolioPosition(asset="Ação X", ticker="X", position_type="notional", position_value=1_000_000)
    dv01_pos = PortfolioPosition(asset="Swap Y", ticker="Y", position_type="dv01", position_value=5_000)
    # Y não tem cotação no dia 3 (feriado local) -- não deve derrubar o dia inteiro do portfólio.
    prices = {
        "X": _series([100.0, 102.0, 103.0]),
        "Y": pd.Series([10.00, 10.05], index=[pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")]),
    }
    pnl = portfolio_pnl_series([notional, dv01_pos], prices)
    assert len(pnl) == 2
    assert pnl.iloc[1] == pytest.approx(1_000_000 * (103.0 / 102.0 - 1))
