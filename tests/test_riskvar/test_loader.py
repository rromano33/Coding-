from pathlib import Path

import pandas as pd
import pytest

from riskvar.loader import PortfolioLoader

COLUMN_MAP = {"asset": "Ativo", "ticker": "Ticker", "position_type": "Tipo", "position_value": "Posicao"}


def _write_xlsx(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "portfolio.xlsx"
    pd.DataFrame(rows).to_excel(path, sheet_name="Portfolio", index=False)
    return path


def test_loads_notional_and_dv01_rows(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [
            {"Ativo": "Ação X", "Ticker": "X US Equity", "Tipo": "Notional", "Posicao": 1_000_000},
            {"Ativo": "Swap Y", "Ticker": "Y Curncy", "Tipo": "DV01", "Posicao": 5_000},
        ],
    )
    positions = PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()
    assert len(positions) == 2
    assert positions[0].position_type == "notional"
    assert positions[1].position_type == "dv01"
    assert positions[1].position_value == 5_000


def test_skips_rows_with_blank_ticker(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [
            {"Ativo": "Ação X", "Ticker": "X US Equity", "Tipo": "Notional", "Posicao": 1_000_000},
            {"Ativo": "", "Ticker": None, "Tipo": "Notional", "Posicao": 0},
        ],
    )
    positions = PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()
    assert len(positions) == 1


def test_raises_on_unrecognized_position_type(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [{"Ativo": "Ação X", "Ticker": "X US Equity", "Tipo": "Duration", "Posicao": 1_000_000}],
    )
    with pytest.raises(ValueError, match="não reconhecido"):
        PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()


def test_raises_if_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        PortfolioLoader(tmp_path / "nope.xlsx", "Portfolio", COLUMN_MAP).load()
