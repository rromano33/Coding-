import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.data.curve_store import save_curve

import build_dashboard  # noqa: E402 (needs the sys.path insert above)

VALUATION_DATE = date(2026, 7, 20)
MEETINGS = [date(2026, 8, 6), date(2026, 9, 17), date(2026, 11, 5), date(2026, 12, 10), date(2027, 1, 28)]


def _settings(tmp_path: Path) -> dict:
    return {
        "paths": {"inputs_bcs": str(tmp_path / "Input_BCs.xlsx")},
        "sheets": {"tickers_sheet": "Tickers", "dates_sheet": "Dates", "positions_sheet": "Posições"},
        "tickers_columns": {"country": "Country", "kind": "Type", "description": "Description", "ticker": "Ticker"},
        "dates_columns": {"meetings": {"BCB": "brazil"}, "holidays": {}},
        "positions_columns": {"TradeID": "TradeID"},
        "reporting": {"meetings_horizon": 3},
    }


def _write_workbook(path: Path) -> None:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"Ticker": [], "Country": [], "Description": [], "Type": []}).to_excel(
            writer, sheet_name="Tickers", index=False
        )
        pd.DataFrame({"BCB": pd.to_datetime(MEETINGS)}).to_excel(writer, sheet_name="Dates", index=False)
        pd.DataFrame({"TradeID": []}).to_excel(writer, sheet_name="Posições", index=False)


def _save_fixture_curve(processed_dir: Path) -> None:
    pillar_dates = MEETINGS
    dfs = [(1.10) ** (-((d - VALUATION_DATE).days / 365)) for d in pillar_dates]
    curve = DiscountCurve(VALUATION_DATE, pillar_dates, dfs, DayCount.ACT_365, Compounding.EXPONENTIAL, None)
    save_curve(curve, processed_dir, "brazil")
    (processed_dir / f"policy_brazil_{VALUATION_DATE}.json").write_text(
        json.dumps({"policy_rate": 0.10, "valuation_date": str(VALUATION_DATE)})
    )


def _save_fixture_report(processed_dir: Path, implied_change_bps: list[float] | None = None) -> None:
    """priced_bc_brazil_<data>.csv -- a MESMA fonte que build_country_data
    (cards/heatmap) e build_lab_section_data (aba de cenários) devem ler,
    pra nunca divergir entre si (ver docstring de lab_data.py)."""
    implied_change_bps = implied_change_bps or [-17.0, -12.0, 0.0, 5.0, 8.0]
    cumulative, running = [], 0.0
    for v in implied_change_bps:
        running += v
        cumulative.append(running)
    df = pd.DataFrame(
        {
            "meeting_date": MEETINGS,
            "level_before_bps": [0.0] * len(MEETINGS),
            "level_after_bps": [0.0] * len(MEETINGS),
            "implied_change_bps": implied_change_bps,
            "cumulative_change_from_spot_bps": cumulative,
        }
    )
    df.to_csv(processed_dir / f"priced_bc_brazil_{VALUATION_DATE}.csv", index=False)


def test_lab_section_data_includes_market_change_bps_per_meeting(tmp_path):
    """build_lab_section_data must pass through lab_data.py's market_change_bps
    field per meeting -- the dashboard's "Mkt Δbps" column reads it directly
    (Ricardo, 29/07/2026: quer ver o que o mercado precifica ao lado do
    cenário digitado, pra comparar direto sem fazer conta)."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)
    _save_fixture_report(processed_dir)
    settings = _settings(tmp_path)

    data = build_dashboard.build_lab_section_data(settings, processed_dir, "brazil", "Brasil")

    assert data is not None
    meetings = data["skeleton"]["meetings"]
    assert meetings and all("market_change_bps" in m for m in meetings)


def test_lab_meetings_match_cards_exactly_same_source_data(tmp_path):
    """Regression: Ricardo (29/07/2026, print de tela) achou a tabela inicial
    (cards) e a tabela de cenários interativos mostrando bps/taxa DIFERENTES
    pra mesma reunião do mesmo país -- cada uma calculava por conta própria
    (cards liam o priced_bc CSV, cenários recomputavam via curve.forward_rate
    direto na curva não suavizada). As duas têm que sair exatamente da mesma
    base agora -- ver docstring de lab_data.py."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)
    _save_fixture_report(processed_dir)
    settings = _settings(tmp_path)

    card_data = build_dashboard.build_country_data(processed_dir, "brazil")
    lab_data = build_dashboard.build_lab_section_data(settings, processed_dir, "brazil", "Brasil")

    assert card_data is not None and lab_data is not None
    lab_meetings = {m["date"]: m for m in lab_data["skeleton"]["meetings"]}
    assert len(card_data["rows"]) == len(lab_meetings)
    for row in card_data["rows"]:
        lab_m = lab_meetings[row["meeting_date"].isoformat()]
        assert lab_m["market_change_bps"] == pytest.approx(row["implied_change_bps"])
        assert lab_m["market_forward_pct"] == pytest.approx(row["rate_pct"])


def test_render_lab_section_has_n_scenario_columns_and_no_meeting_results_table(tmp_path):
    """Ricardo (29/07/2026): quer rodar pelo menos 4 cenários alternativos lado
    a lado, e quer que o resultado do "Calcular" mostre só a tabela de impacto
    por vértice (a tabela de reunião-a-reunião foi removida -- os cenários já
    ficam visíveis na própria tabela de input)."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)
    _save_fixture_report(processed_dir)
    settings = _settings(tmp_path)

    data = build_dashboard.build_lab_section_data(settings, processed_dir, "brazil", "Brasil")
    html = build_dashboard.render_lab_section([data])

    assert html.count('class="lab-scenario-name"') == build_dashboard.LAB_N_SCENARIOS
    assert html.count('class="lab-bps-input"') == build_dashboard.LAB_N_SCENARIOS * len(data["skeleton"]["meetings"])
    assert "lab-meeting-tbody" not in html
    assert "lab-vertex-thead-brazil" in html


def test_render_country_card_shows_rate_next_to_meeting_date(tmp_path):
    """Ricardo (29/07/2026): quer a taxa da reunião ao lado da data, na
    tabela de cada país, e a data numa linha só (sem quebrar)."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _save_fixture_curve(processed_dir)
    _save_fixture_report(processed_dir)

    card_data = build_dashboard.build_country_data(processed_dir, "brazil")
    html = build_dashboard.render_country_card(card_data)

    assert '<th class="num">Taxa</th>' in html
    assert build_dashboard.fmt_pct(card_data["rows"][0]["rate_pct"]) in html
