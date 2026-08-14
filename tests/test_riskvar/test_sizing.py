from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.sizing import change_series, size_position, vol_stats, vol_stats_by_window


def _series(values: list[float]) -> pd.Series:
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=pd.to_datetime(dates))


def test_change_series_pct_is_percentage_return():
    prices = _series([100.0, 102.0, 101.0])
    changes = change_series(prices, "pct")
    assert changes.iloc[0] == pytest.approx((102.0 / 100.0 - 1) * 100.0)
    assert changes.iloc[1] == pytest.approx((101.0 / 102.0 - 1) * 100.0)


def test_change_series_bps_is_diff_times_100():
    yields_pct = _series([10.00, 10.05, 9.95])
    changes = change_series(yields_pct, "bps")
    assert changes.iloc[0] == pytest.approx(5.0)
    assert changes.iloc[1] == pytest.approx(-10.0)


def test_change_series_rejects_unknown_kind():
    with pytest.raises(ValueError):
        change_series(_series([1.0, 2.0]), "notional")


def test_vol_stats_matches_manual_std_and_annualization():
    changes = _series([1.0, -2.0, 0.5, -0.5, 1.5])
    stats = vol_stats(changes, trading_days_per_year=252)
    assert stats.n_obs == 5
    assert stats.daily_vol == pytest.approx(changes.std(ddof=1))
    assert stats.annualized_vol == pytest.approx(stats.daily_vol * (252 ** 0.5))
    assert stats.mean == pytest.approx(changes.mean())
    assert stats.median == pytest.approx(changes.median())


def test_vol_stats_zero_vol_series_has_zero_skew_and_kurtosis_no_crash():
    changes = _series([0.0, 0.0, 0.0])
    stats = vol_stats(changes)
    assert stats.daily_vol == 0.0
    assert stats.skew == 0.0
    assert stats.excess_kurtosis == 0.0


def test_vol_stats_by_window_returns_one_row_per_window():
    changes = _series([float(i % 5 - 2) for i in range(100)])
    df = vol_stats_by_window(changes, {"7D": 7, "30D": 30})
    assert list(df["janela"]) == ["7D", "30D"]
    assert (df["vol_diaria"] >= 0).all()


def test_vol_stats_by_window_skips_window_larger_than_available_history():
    changes = _series([1.0, -1.0, 2.0])
    df = vol_stats_by_window(changes, {"3D": 3, "60D": 60})
    assert list(df["janela"]) == ["3D", "60D"]  # tail() com poucos dados só devolve o que tem, não fica vazio


def test_size_position_long_notional_stop_below_target_above():
    result = size_position(
        trade_price=1.1564, daily_vol=0.42, stop_multiple=1.5, reward_risk=2.0,
        max_loss=50_000, side="long", kind="pct",
    )
    stop_pct = 1.5 * 0.42 / 100.0
    expected_stop_price = 1.1564 * (1 - stop_pct)
    expected_target_price = 1.1564 + 2.0 * (1.1564 - expected_stop_price)
    expected_size = 50_000 / stop_pct

    assert result.stop_price == pytest.approx(expected_stop_price)
    assert result.target_price == pytest.approx(expected_target_price)
    assert result.size == pytest.approx(expected_size)
    assert result.stop_price < 1.1564 < result.target_price


def test_size_position_short_stop_above_target_below():
    result = size_position(
        trade_price=100.0, daily_vol=1.0, stop_multiple=2.0, reward_risk=1.5,
        max_loss=10_000, side="short", kind="pct",
    )
    assert result.stop_price > 100.0
    assert result.target_price < 100.0


def test_size_position_bps_kind_gives_dv01_sized_directly_by_bps_move():
    result = size_position(
        trade_price=10.00, daily_vol=5.0, stop_multiple=1.0, reward_risk=2.0,
        max_loss=25_000, side="long", kind="bps",
    )
    # stop_move = 1.0 * 5.0 = 5 bps -> distância de preço = 0.05 (pontos de taxa)
    assert result.stop_move == pytest.approx(5.0)
    assert result.stop_price == pytest.approx(10.00 - 0.05)
    assert result.size == pytest.approx(25_000 / 5.0)  # DV01 = maxloss / stop em bps


def test_size_position_zero_vol_gives_zero_size_no_crash():
    result = size_position(
        trade_price=100.0, daily_vol=0.0, stop_multiple=1.5, reward_risk=2.0,
        max_loss=10_000, side="long", kind="pct",
    )
    assert result.size == 0.0
    assert result.stop_price == pytest.approx(100.0)


def test_size_position_rejects_invalid_side_and_kind():
    with pytest.raises(ValueError):
        size_position(100.0, 1.0, 1.5, 2.0, 1000.0, side="up", kind="pct")
    with pytest.raises(ValueError):
        size_position(100.0, 1.0, 1.5, 2.0, 1000.0, side="long", kind="percent")
