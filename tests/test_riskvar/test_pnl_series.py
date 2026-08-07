from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.loader import PortfolioPosition
from riskvar.pnl_series import (
    diversification_benefit,
    filter_positions_with_history,
    portfolio_pnl_series,
    position_pnl_series,
    risk_contribution_pct,
    worst_days,
)
from riskvar.var_metrics import historical_var


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


def test_filter_positions_with_history_drops_tickers_bbg_never_returned():
    # bdh às vezes omite a coluna inteira (não NaN, ausente mesmo) para um
    # ticker sem dado nenhum no range pedido -- isso não pode derrubar o
    # cálculo do resto do portfólio.
    kept_position = PortfolioPosition(asset="Ação X", ticker="X", position_type="notional", position_value=1_000_000)
    orphan_position = PortfolioPosition(asset="FX Y", ticker="AUDCAD Curncy", position_type="notional", position_value=500_000)
    kept, missing = filter_positions_with_history([kept_position, orphan_position], available_tickers=["X"])
    assert kept == [kept_position]
    assert missing == ["AUDCAD Curncy"]


def test_filter_positions_with_history_keeps_everything_when_all_tickers_present():
    position = PortfolioPosition(asset="Ação X", ticker="X", position_type="notional", position_value=1_000_000)
    kept, missing = filter_positions_with_history([position], available_tickers=["X", "Y"])
    assert kept == [position]
    assert missing == []


def _dv01_position_with_bps_path(asset, ticker, dv01, bps_changes):
    # diff(yields)*100 == bps_changes exatamente, então o P&L da posição
    # (dv01 * diff_bps) fica sob controle total do teste.
    levels = [0.0]
    for bps in bps_changes:
        levels.append(levels[-1] + bps / 100.0)
    position = PortfolioPosition(asset=asset, ticker=ticker, position_type="dv01", position_value=dv01)
    return position, _series(levels)


def test_risk_contribution_sums_to_100_and_is_positive_for_a_dominant_position():
    dominant, dominant_prices = _dv01_position_with_bps_path("Dominante", "D", 1.0, [10, -10, 10, -10, 10, -8])
    small, small_prices = _dv01_position_with_bps_path("Pequena", "S", 1.0, [1, -1, 2, -1, 1, -1])
    positions = [dominant, small]
    prices = {"D": dominant_prices, "S": small_prices}

    contributions = risk_contribution_pct(positions, prices)

    assert sum(contributions) == pytest.approx(100.0, abs=1e-6)
    assert contributions[0] > contributions[1]


def test_risk_contribution_is_negative_for_a_partial_hedge():
    dominant, dominant_prices = _dv01_position_with_bps_path("Dominante", "D", 1.0, [10, -10, 10, -10, 10, -8])
    # Se move majoritariamente contra a posição dominante -- reduz o risco
    # do portfólio, não deveria "comer" uma fatia positiva do total.
    hedge, hedge_prices = _dv01_position_with_bps_path("Hedge", "H", 1.0, [-4, 4, -4, 4, -4, 3])
    positions = [dominant, hedge]
    prices = {"D": dominant_prices, "H": hedge_prices}

    contributions = risk_contribution_pct(positions, prices)

    assert sum(contributions) == pytest.approx(100.0, abs=1e-6)
    assert contributions[1] < 0
    assert contributions[0] > 100.0  # o hedge "devolve" a diferença até fechar em 100%


def test_risk_contribution_falls_back_to_equal_split_when_portfolio_has_zero_variance():
    long_pos, long_prices = _dv01_position_with_bps_path("Comprado", "L", 1.0, [10, -10, 10, -10])
    short_pos, short_prices = _dv01_position_with_bps_path("Vendido", "V", -1.0, [10, -10, 10, -10])
    positions = [long_pos, short_pos]
    prices = {"L": long_prices, "V": short_prices}

    contributions = risk_contribution_pct(positions, prices)

    assert contributions == [50.0, 50.0]


def test_risk_contribution_empty_positions_returns_empty_list():
    assert risk_contribution_pct([], {}) == []


def test_diversification_benefit_is_zero_for_perfectly_correlated_positions():
    pos1, prices1 = _dv01_position_with_bps_path("A", "A", 1.0, [10, -10, 10, -10, 10, -8])
    pos2, prices2 = _dv01_position_with_bps_path("B", "B", 1.0, [10, -10, 10, -10, 10, -8])  # idêntico
    result = diversification_benefit([pos1, pos2], {"A": prices1, "B": prices2}, confidence=0.95)
    assert result.benefit_pct == pytest.approx(0.0, abs=1e-6)
    assert result.portfolio_var == pytest.approx(result.standalone_var_sum, rel=1e-6)


def test_diversification_benefit_is_100pct_for_a_perfect_hedge():
    pos1, prices1 = _dv01_position_with_bps_path("A", "A", 1.0, [10, -10, 10, -10, 10, -8])
    pos2, prices2 = _dv01_position_with_bps_path("B", "B", -1.0, [10, -10, 10, -10, 10, -8])  # espelha o P&L de A
    result = diversification_benefit([pos1, pos2], {"A": prices1, "B": prices2}, confidence=0.95)
    assert result.portfolio_var == pytest.approx(0.0, abs=1e-6)
    assert result.benefit_pct == pytest.approx(100.0, abs=1e-6)
    assert result.standalone_var_sum > 0


def test_diversification_benefit_matches_manual_historical_var_calc():
    pos1, prices1 = _dv01_position_with_bps_path("A", "A", 1.0, [10, -10, 10, -10, 10, -8])
    pos2, prices2 = _dv01_position_with_bps_path("B", "B", 1.0, [3, -6, 9, -3, 6, -5])
    positions, prices = [pos1, pos2], {"A": prices1, "B": prices2}
    result = diversification_benefit(positions, prices, confidence=0.95)

    pnl1 = position_pnl_series(pos1, prices1)
    pnl2 = position_pnl_series(pos2, prices2)
    expected_standalone_sum = historical_var(pnl1, 0.95) + historical_var(pnl2, 0.95)
    expected_portfolio_var = historical_var(pnl1 + pnl2, 0.95)
    assert result.standalone_var_sum == pytest.approx(expected_standalone_sum)
    assert result.portfolio_var == pytest.approx(expected_portfolio_var)


def test_diversification_benefit_empty_positions_returns_zeros():
    result = diversification_benefit([], {}, confidence=0.95)
    assert result.standalone_var_sum == 0.0
    assert result.portfolio_var == 0.0
    assert result.benefit_pct == 0.0


def test_worst_days_returns_n_lowest_pnl_sorted_ascending():
    pnl = _series([100.0, -50.0, 30.0, -200.0, 10.0, -75.0])
    result = worst_days(pnl, n=3)
    assert len(result) == 3
    assert list(result["pnl"]) == [-200.0, -75.0, -50.0]


def test_worst_days_dates_match_original_series_index():
    pnl = _series([10.0, -300.0, 5.0])
    result = worst_days(pnl, n=1)
    assert result.iloc[0]["pnl"] == -300.0
    assert result.iloc[0]["data"] == date(2026, 1, 2)
