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


def test_invalid_scenario_file_is_skipped_not_fatal(tmp_path, monkeypatch):
    """A scenario yaml whose meeting_date isn't in the modeled horizon (e.g. an
    unedited exemplo_template.yaml) must not take down the whole dashboard
    build — it should be skipped with a message, other scenarios still render."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    _write_workbook(tmp_path / "Input_BCs.xlsx")
    _save_fixture_curve(processed_dir)

    scenarios_dir = tmp_path / "scenarios" / "brazil"
    scenarios_dir.mkdir(parents=True)
    (scenarios_dir / "valid.yaml").write_text(
        f"name: Valid\ncountry: brazil\nshocks:\n  - meeting_date: {MEETINGS[1]}\n    shock_bps: -25\n"
    )
    (scenarios_dir / "unedited_template.yaml").write_text(
        "name: Template\ncountry: brazil\nshocks:\n  - meeting_date: 2099-01-01\n    shock_bps: -25\n"
    )

    monkeypatch.setattr(build_dashboard, "SCENARIOS_DIR", tmp_path / "scenarios")
    settings = _settings(tmp_path)

    data = build_dashboard.build_scenario_section_data(settings, processed_dir, "brazil", "Brasil")

    assert data is not None
    assert list(data["scenario_labels"]) == ["valid"]  # unedited_template.yaml silently skipped
