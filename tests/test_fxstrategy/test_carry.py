from datetime import date, timedelta

import pandas as pd
import pytest

from fxstrategy.carry import (
    FWD_POINTS_SCALE,
    TENOR_DAYS,
    CarryLeg,
    align_carry_inputs,
    carry_series,
    forward_premium,
    leg_premium_series,
)


def _series(values: list[float], start: date = date(2026, 1, 1)) -> pd.Series:
    dates = [start + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=pd.to_datetime(dates))


def test_forward_premium_matches_manual_calc():
    spot = _series([5.0, 5.0, 5.0])
    points = _series([1000.0, 1000.0, 1000.0])
    premium = forward_premium(spot, points, scale=10_000.0, tenor_days=90)
    expected = (1000.0 / 10_000.0) / 5.0 * (365.0 / 90.0)
    assert premium.tolist() == pytest.approx([expected] * 3)


def test_forward_premium_negative_points_gives_negative_premium():
    # JPY: pontos negativos (JPY mais barato que USD) -> prêmio negativo.
    spot = _series([150.0, 150.0])
    points = _series([-40.0, -40.0])
    premium = forward_premium(spot, points, scale=100.0, tenor_days=30)
    assert (premium < 0).all()


def test_align_carry_inputs_keeps_only_common_dates():
    spot = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]))
    points = pd.Series([10.0, 20.0, 30.0], index=pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"]))
    aligned_spot, aligned_points = align_carry_inputs(spot, points)
    assert list(aligned_spot.index) == list(pd.to_datetime(["2026-01-02", "2026-01-03"]))
    assert list(aligned_spot.values) == [2.0, 3.0]
    assert list(aligned_points.values) == [10.0, 20.0]


def test_leg_premium_series_raises_on_missing_ticker():
    leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    with pytest.raises(KeyError, match="BCN3M Curncy"):
        leg_premium_series({"USDBRL Curncy": _series([5.0, 5.0])}, leg)


def test_leg_premium_series_computes_from_price_histories():
    leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    price_histories = {
        "USDBRL Curncy": _series([5.0, 5.0]),
        "BCN3M Curncy": _series([1000.0, 1000.0]),
    }
    premium = leg_premium_series(price_histories, leg)
    expected = (1000.0 / 10_000.0) / 5.0 * (365.0 / 90.0)
    assert premium.tolist() == pytest.approx([expected] * 2)


def test_carry_series_without_funding_leg_returns_em_premium_unchanged():
    em_leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    price_histories = {
        "USDBRL Curncy": _series([5.0, 5.0]),
        "BCN3M Curncy": _series([1000.0, 1000.0]),
    }
    carry = carry_series(price_histories, em_leg)
    expected = leg_premium_series(price_histories, em_leg)
    assert carry.tolist() == pytest.approx(expected.tolist())


def test_carry_series_subtracts_funding_leg_premium():
    em_leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    funding_leg = CarryLeg(currency="JPY", spot_ticker="USDJPY Curncy", points_ticker="JPY3M Curncy", scale=100.0, tenor_days=90)
    price_histories = {
        "USDBRL Curncy": _series([5.0, 5.0]),
        "BCN3M Curncy": _series([1000.0, 1000.0]),
        "USDJPY Curncy": _series([150.0, 150.0]),
        "JPY3M Curncy": _series([-112.0, -112.0]),
    }
    carry = carry_series(price_histories, em_leg, funding_leg)
    em_premium = leg_premium_series(price_histories, em_leg)
    jpy_premium = leg_premium_series(price_histories, funding_leg)
    assert carry.tolist() == pytest.approx((em_premium - jpy_premium).tolist())


def test_carry_funded_in_low_yield_currency_is_larger_than_funded_in_usd():
    # Financiar numa moeda de yield MENOR que USD (JPY, prêmio negativo)
    # deve dar carry MAIOR do que financiar em USD direto -- essa é
    # literalmente a razão de preferir JPY como funding.
    em_leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    funding_leg = CarryLeg(currency="JPY", spot_ticker="USDJPY Curncy", points_ticker="JPY3M Curncy", scale=100.0, tenor_days=90)
    price_histories = {
        "USDBRL Curncy": _series([5.0, 5.0]),
        "BCN3M Curncy": _series([1000.0, 1000.0]),
        "USDJPY Curncy": _series([150.0, 150.0]),
        "JPY3M Curncy": _series([-112.0, -112.0]),
    }
    carry_vs_usd = carry_series(price_histories, em_leg)
    carry_vs_jpy = carry_series(price_histories, em_leg, funding_leg)
    assert (carry_vs_jpy > carry_vs_usd).all()


def test_carry_series_aligns_by_intersection_when_legs_have_different_calendars():
    em_leg = CarryLeg(currency="BRL", spot_ticker="USDBRL Curncy", points_ticker="BCN3M Curncy", scale=10_000.0, tenor_days=90)
    funding_leg = CarryLeg(currency="JPY", spot_ticker="USDJPY Curncy", points_ticker="JPY3M Curncy", scale=100.0, tenor_days=90)
    price_histories = {
        "USDBRL Curncy": _series([5.0, 5.0, 5.0]),
        "BCN3M Curncy": _series([1000.0, 1000.0, 1000.0]),
        # JPY só tem histórico nos últimos 2 dias (feriado local no primeiro, por ex.)
        "USDJPY Curncy": _series([150.0, 150.0], start=date(2026, 1, 2)),
        "JPY3M Curncy": _series([-112.0, -112.0], start=date(2026, 1, 2)),
    }
    carry = carry_series(price_histories, em_leg, funding_leg)
    assert len(carry) == 2


def test_fwd_points_scale_and_tenor_constants_match_terminal_confirmation():
    # Documentação viva do que foi confirmado na tela DES de cada ticker
    # (ver conversa) -- muda aqui só se reconfirmar no terminal.
    assert FWD_POINTS_SCALE == {"JPY": 100.0, "BRL": 10_000.0, "MXN": 10_000.0, "ZAR": 10_000.0}
    assert TENOR_DAYS == {"1M": 30, "3M": 90}
