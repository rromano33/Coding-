from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.html_report import render_report_html, save_standalone_html
from riskvar.loader import PortfolioPosition
from riskvar.report import build_risk_report


def _synthetic_performance_series(n_days: int = 252) -> pd.Series:
    dates = [date(2025, 7, 23) + timedelta(days=i) for i in range(n_days)]
    values = [1000.0 * ((i % 7) - 3) for i in range(n_days)]  # oscila em torno de 0
    return pd.Series(values, index=pd.to_datetime(dates)).cumsum()


def _sample_report_df() -> pd.DataFrame:
    pnl_3m = pd.Series([100.0, -200.0, 300.0, -50.0] * 16)  # 64 obs
    pnl_12m = _synthetic_performance_series(252).diff().dropna()
    return build_risk_report({"3M": pnl_3m, "12M": pnl_12m}, [0.95], 252)


def _sample_positions() -> list[PortfolioPosition]:
    return [
        PortfolioPosition(asset="ES1", ticker="ES1 Index", position_type="notional", position_value=10_000_000, asset_class="Equity"),
        PortfolioPosition(asset="Swap Y", ticker="Y Curncy", position_type="dv01", position_value=5_000, asset_class="EM Rates"),
    ]


def _sample_contributions() -> dict[str, list[float]]:
    return {"3M": [70.0, 30.0], "12M": [65.0, 35.0]}


def test_render_report_html_contains_key_sections():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    html = render_report_html(
        report_df,
        performance,
        date(2026, 7, 23),
        n_positions=2,
        positions=_sample_positions(),
        contributions_by_window=_sample_contributions(),
        primary_window="12M",
    )

    assert "Risco de portfólio" in html
    assert "2 posições" in html
    assert "VaR histórico" in html
    assert "class=\"perf-chart\"" in html
    assert "<script>" in html
    assert "Ativos do portfólio e contribuição ao risco" in html
    assert "ES1" in html
    assert "+65.0%" in html
    assert "+35.0%" in html
    # no doctype/html/head/body -- this is a content fragment, not a full document
    assert "<!doctype" not in html.lower()
    assert "<html" not in html.lower()


def test_render_report_html_sorts_positions_by_absolute_contribution_in_primary_window():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="Pequena", ticker="A", position_type="notional", position_value=1_000),
        PortfolioPosition(asset="Dominante", ticker="B", position_type="notional", position_value=9_000),
    ]
    contributions = {"3M": [10.0, 90.0], "12M": [-80.0, 20.0]}  # ordenar pela 12M -> Pequena (80) antes de Dominante (20)

    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=2,
        positions=positions, contributions_by_window=contributions, primary_window="12M",
    )

    assert html.index("Pequena") < html.index("Dominante")
    assert "-80.0%" in html


def test_render_report_html_escapes_asset_names_from_the_spreadsheet():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="<script>alert(1)</script>", ticker="A", position_type="notional", position_value=1_000, asset_class="Equity"),
    ]
    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=1,
        positions=positions, contributions_by_window={"3M": [100.0], "12M": [100.0]}, primary_window="12M",
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_report_html_skips_positions_table_when_empty():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=0,
        positions=[], contributions_by_window={"3M": [], "12M": []}, primary_window="12M",
    )
    assert "Ativos do portfólio e contribuição ao risco" not in html


def test_render_report_html_handles_single_day_performance_series():
    report_df = _sample_report_df()
    performance = pd.Series([500.0], index=[pd.Timestamp("2026-07-23")])
    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=2,
        positions=_sample_positions(), contributions_by_window=_sample_contributions(), primary_window="12M",
    )
    assert "perf-chart" in html


def test_save_standalone_html_wraps_content_in_full_document(tmp_path):
    content = "<div>oi</div>"
    out_path = tmp_path / "report.html"
    save_standalone_html(content, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "<div>oi</div>" in text
    assert "<title>" in text
