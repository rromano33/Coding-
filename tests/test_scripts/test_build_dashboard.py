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


def test_lab_section_data_includes_market_change_bps_per_meeting(tmp_path):
    """build_lab_section_data must pass through lab_data.py's market_change_bps
    field per meeting -- the dashboard's "Mkt Δbps" column reads it directly
    (Ricardo, 29/07/2026: quer ver o que o mercado precifica ao lado do
    cenário digitado, pra comparar direto sem fazer conta)."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)
    settings = _settings(tmp_path)

    data = build_dashboard.build_lab_section_data(settings, processed_dir, "brazil", "Brasil")

    assert data is not None
    meetings = data["skeleton"]["meetings"]
    assert meetings and all("market_change_bps" in m for m in meetings)


def test_render_lab_section_has_n_scenario_columns_and_no_meeting_results_table(tmp_path):
    """Ricardo (29/07/2026): quer rodar pelo menos 4 cenários alternativos lado
    a lado, e quer que o resultado do "Calcular" mostre só a tabela de impacto
    por vértice (a tabela de reunião-a-reunião foi removida -- os cenários já
    ficam visíveis na própria tabela de input)."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)
    settings = _settings(tmp_path)

    data = build_dashboard.build_lab_section_data(settings, processed_dir, "brazil", "Brasil")
    html = build_dashboard.render_lab_section([data])

    assert html.count('class="lab-scenario-name"') == build_dashboard.LAB_N_SCENARIOS
    assert html.count('class="lab-bps-input"') == build_dashboard.LAB_N_SCENARIOS * len(data["skeleton"]["meetings"])
    assert "lab-meeting-tbody" not in html
    assert "lab-vertex-thead-brazil" in html
