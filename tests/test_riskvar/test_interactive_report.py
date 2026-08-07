from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from riskvar.interactive_report import _price_history_payload, render_interactive_html


def _synthetic_price_series(n_days: int = 260, start: float = 100.0) -> pd.Series:
    dates = pd.bdate_range(end=date(2026, 8, 7), periods=n_days)
    values = [start + (i % 11) * 0.3 for i in range(n_days)]
    return pd.Series(values, index=dates)


def _sample_price_histories() -> dict[str, pd.Series]:
    return {
        "A Index": _synthetic_price_series(260, 100.0),
        "B Curncy": _synthetic_price_series(260, 5.0),
        "SPX Index": _synthetic_price_series(260, 5000.0),
    }


def test_price_history_payload_trims_to_max_days_and_formats_dates():
    histories = _sample_price_histories()
    payload = _price_history_payload(histories, max_days=10)

    assert set(payload.keys()) == {"A Index", "B Curncy", "SPX Index"}
    assert len(payload["A Index"]) == 10
    first_date, first_value = payload["A Index"][0]
    assert isinstance(first_date, str)
    date.fromisoformat(first_date)  # não levanta -- formato ISO válido
    assert isinstance(first_value, float)
    # ordem ascendente (mais recente por último), mesma convenção do resto do projeto
    all_dates = [d for d, _ in payload["A Index"]]
    assert all_dates == sorted(all_dates)


def test_price_history_payload_drops_nan():
    series = _synthetic_price_series(20, 100.0)
    series.iloc[5] = float("nan")
    payload = _price_history_payload({"X Index": series}, max_days=20)
    assert len(payload["X Index"]) == 19


def _render_sample(**overrides) -> str:
    kwargs = dict(
        price_histories=_sample_price_histories(),
        lookback_windows={"3M": 63, "12M": 252},
        confidence_levels=[0.95, 0.99],
        trading_days_per_year=252,
        base_currency="USD",
        valuation_date=date(2026, 8, 7),
        generated_at=datetime(2026, 8, 7, 18, 30),
    )
    kwargs.update(overrides)
    return render_interactive_html(**kwargs)


def test_render_interactive_html_shows_explicit_snapshot_date():
    html = _render_sample()
    assert "07/08/2026" in html
    assert "18:30" in html
    assert "FOTO estática" in html
    assert "não se conecta à Bloomberg" in html


def test_render_interactive_html_embeds_price_history_and_no_positions():
    html = _render_sample()
    assert "const PRICE_HISTORY" in html
    assert "A Index" in html
    assert "SPX Index" in html
    # nenhuma posição/valor de posição real deve vir embutido -- só preço de mercado
    assert "position_value" not in html
    assert "PortfolioPosition" not in html


def test_render_interactive_html_embeds_config():
    html = _render_sample()
    assert "const CONFIG" in html
    assert "confidence_levels" in html or "0.95" in html
    assert "lookback_windows" in html or "63" in html


def test_render_interactive_html_includes_stress_config_when_provided():
    html = _render_sample(
        stress_factors={"spx": {"ticker": "SPX Index", "kind": "pct_return"}},
        stress_scenarios=[{"name": "S&P -5%", "shocks": {"spx": -0.05}}],
    )
    assert "stress_factors" in html
    assert "S&P -5%" in html or "S\\u0026P -5%" in html


def test_render_interactive_html_omits_stress_when_not_configured():
    html = _render_sample()
    assert '"stress_factors": {}' in html or '"stress_factors":{}' in html


def test_render_interactive_html_no_script_injection_from_ticker_names():
    histories = _sample_price_histories()
    histories["</script><script>alert(1)</script> Index"] = _synthetic_price_series(20, 1.0)
    html = render_interactive_html(
        histories, {"3M": 10}, [0.95], 252, "USD", date(2026, 8, 7), datetime(2026, 8, 7, 12, 0)
    )
    assert "</script><script>alert(1)</script>" not in html
