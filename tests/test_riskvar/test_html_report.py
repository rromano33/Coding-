from datetime import date, timedelta

import pandas as pd
import pytest

from riskvar.html_report import (
    _group_and_cap,
    _group_contributions,
    _label_ink_for,
    render_report_html,
    save_standalone_html,
)
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


def test_positions_table_is_sortable_with_raw_numeric_sort_values():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="ES1", ticker="A", position_type="notional", position_value=-3_000_000.0, asset_class="Equity"),
    ]
    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=1,
        positions=positions, contributions_by_window={"3M": [42.5], "12M": [-8.25]}, primary_window="12M",
    )

    assert 'id="positions-table"' in html
    assert "sortable-table" in html
    assert '__initSortableTable("positions-table")' in html
    # valor bruto (não formatado) disponível pro JS ordenar numericamente
    assert 'data-sort-value="-3000000.0"' in html
    assert 'data-sort-value="-8.25"' in html
    # a coluna da janela primária já nasce marcada como ordenada
    assert 'aria-sort="descending"' in html


def test_positions_table_groups_by_class_with_subtotal_rows():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="ES1", ticker="A", position_type="notional", position_value=10_000_000, asset_class="Equity"),
        PortfolioPosition(asset="EWZ", ticker="B", position_type="notional", position_value=-3_000_000, asset_class="Equity"),
        PortfolioPosition(asset="AUDUSD", ticker="C", position_type="notional", position_value=5_000_000, asset_class="FX"),
    ]
    contributions = {"3M": [50.0, 30.0, 20.0], "12M": [70.0, -10.0, 40.0]}

    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=3,
        positions=positions, contributions_by_window=contributions, primary_window="12M",
    )

    # duas classes -> dois <tbody>, cada um com sua própria linha de grupo
    assert html.count('<tbody><tr class="group-header-row"') == 2
    assert '<span class="group-name">Equity</span>' in html
    assert '<span class="group-name">FX</span>' in html
    # subtotal da classe Equity na 12M = 70 + (-10) = 60
    assert "12M: +60.0%" in html
    # a coluna "Classe" não existe mais como coluna própria -- é o cabeçalho do grupo
    assert "<th data-sort=\"text\">Classe</th>" not in html
    # classe com maior |contribuição| (FX, 40) vem depois de Equity (60) na ordenação por grupo primário
    assert html.index("Equity") < html.index("FX")


def test_sortable_script_preserves_group_header_rows():
    # A linha de grupo tem que ficar de fora do reordenamento por coluna
    # (senão a agrupação por classe se perderia ao clicar num cabeçalho).
    from riskvar.html_report import _SORTABLE_TABLE_SCRIPT

    assert "tr:not(.group-header-row)" in _SORTABLE_TABLE_SCRIPT


def test_pie_charts_present_for_class_and_asset_breakdown():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="ES1", ticker="A", position_type="notional", position_value=10_000_000, asset_class="Equity"),
        PortfolioPosition(asset="EWZ", ticker="B", position_type="notional", position_value=-3_000_000, asset_class="Equity"),
        PortfolioPosition(asset="AUDUSD", ticker="C", position_type="notional", position_value=5_000_000, asset_class="FX"),
    ]
    contributions = {"3M": [50.0, 30.0, 20.0], "12M": [70.0, -10.0, 40.0]}

    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=3,
        positions=positions, contributions_by_window=contributions, primary_window="12M",
    )

    assert 'id="pie-class"' in html
    assert 'id="pie-asset"' in html
    assert "Contribuição por classe · 12M" in html
    assert "Contribuição por ativo · 12M" in html
    assert "(hedge)" in html  # EWZ tem contribuição negativa na 12M


def test_pie_chart_json_payload_is_safe_against_script_breakout():
    report_df = _sample_report_df()
    performance = _synthetic_performance_series(252)
    positions = [
        PortfolioPosition(asset="</script><script>alert(1)</script>", ticker="A", position_type="notional", position_value=1_000, asset_class="Equity"),
    ]
    html = render_report_html(
        report_df, performance, date(2026, 7, 23), n_positions=1,
        positions=positions, contributions_by_window={"3M": [100.0], "12M": [100.0]}, primary_window="12M",
    )
    assert "</script><script>alert(1)</script>" not in html


def test_group_and_cap_folds_extra_entries_into_outros():
    entries = [(f"A{i}", float(i + 1)) for i in range(9)]  # 9 entradas, cap padrão é 7
    grouped = _group_and_cap(entries)
    assert len(grouped) == 8  # 7 + Outros
    assert grouped[-1][0] == "Outros"
    assert grouped[-1][1] == pytest.approx(1.0 + 2.0)  # soma assinada das 2 menores (A0=1, A1=2)


def test_group_and_cap_keeps_everything_under_the_cap():
    entries = [("A", 10.0), ("B", -5.0)]
    assert _group_and_cap(entries) == [("A", 10.0), ("B", -5.0)]


def test_group_contributions_sums_by_key():
    positions = [
        PortfolioPosition(asset="ES1", ticker="A", position_type="notional", position_value=1, asset_class="Equity"),
        PortfolioPosition(asset="EWZ", ticker="B", position_type="notional", position_value=1, asset_class="Equity"),
        PortfolioPosition(asset="AUDUSD", ticker="C", position_type="notional", position_value=1, asset_class="FX"),
    ]
    contributions = [40.0, 25.0, 35.0]
    grouped = dict(_group_contributions(positions, contributions, lambda p: p.asset_class))
    assert grouped["Equity"] == pytest.approx(65.0)
    assert grouped["FX"] == pytest.approx(35.0)


def test_label_ink_is_dark_on_light_fills_and_light_on_dark_fills():
    assert _label_ink_for("#eda100") == "#0b0b0b"  # amarelo, claro -- precisa de texto escuro
    assert _label_ink_for("#008300") == "#ffffff"  # verde escuro -- precisa de texto claro


def test_save_standalone_html_wraps_content_in_full_document(tmp_path):
    content = "<div>oi</div>"
    out_path = tmp_path / "report.html"
    save_standalone_html(content, out_path)
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert "<div>oi</div>" in text
    assert "<title>" in text
