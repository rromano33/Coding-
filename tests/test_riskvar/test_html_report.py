from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.html_report import render_report_html, save_standalone_html
from riskvar.report import build_risk_report


def _synthetic_performance_series(n_days: int = 252) -> pd.Series:
    dates = [date(2025, 7, 23) + timedelta(days=i) for i in range(n_days)]
    values = [1000.0 * ((i % 7) - 3) for i in range(n_days)]  # oscila em torno de 0
    return pd.Series(values, index=pd.to_datetime(dates)).cumsum()


def _sample_report_df() -> pd.DataFrame:
    pnl_3m = pd.Series([100.0, -200.0, 300.0, -50.0] * 16)  # 64 obs
    pnl_12m = _synthetic_performance_series(252).diff().dropna()
    return build_risk_report({"3M": pnl_3m, "12M": pnl_12m}, [0.95], 252)


def test_render_report_html_contains_key_sections():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    html = render_report_html(report_df, performance, date(2026, 7, 23), n_positions=37)

    assert "Risco de portfólio" in html
    assert "37 posições" in html
    assert "VaR histórico" in html
    assert "class=\"perf-chart\"" in html
    assert "<script>" in html
    # no doctype/html/head/body -- this is a content fragment, not a full document
    assert "<!doctype" not in html.lower()
    assert "<html" not in html.lower()


def test_render_report_html_handles_single_day_performance_series():
    report_df = _sample_report_df()
    performance = pd.Series([500.0], index=[pd.Timestamp("2026-07-23")])
    html = render_report_html(report_df, performance, date(2026, 7, 23), n_positions=1)
    assert "perf-chart" in html


def test_save_standalone_html_wraps_content_in_full_document(tmp_path):
    content = "<div>oi</div>"
    out_path = tmp_path / "report.html"
    save_standalone_html(content, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "<div>oi</div>" in text
    assert "<title>" in text
