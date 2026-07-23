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


def test_matches_headers_case_insensitively_and_ignoring_whitespace(tmp_path):
    # Planilha real usa "BBG" e "Posição" (com espaço/acento) -- o config
    # pode não bater exatamente com a caixa/acentuação real.
    path = _write_xlsx(
        tmp_path,
        [{"ativo": "ES1", "bbg ": "ES1 Index", "TIPO": "Notional", " Posição": 10_000_000}],
    )
    column_map = {"asset": "Ativo", "ticker": "BBG", "position_type": "Tipo", "position_value": "Posição"}
    positions = PortfolioLoader(path, "Portfolio", column_map).load()
    assert len(positions) == 1
    assert positions[0].ticker == "ES1 Index"
    assert positions[0].position_value == 10_000_000


def test_optional_asset_class_column_defaults_when_absent(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [{"Ativo": "ES1", "Ticker": "ES1 Index", "Tipo": "Notional", "Posicao": 10_000_000}],
    )
    positions = PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()
    assert positions[0].asset_class == "N/A"


def test_optional_asset_class_column_read_when_configured(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [{"Classe": "Equity", "Ativo": "ES1", "Ticker": "ES1 Index", "Tipo": "Notional", "Posicao": 10_000_000}],
    )
    column_map = {**COLUMN_MAP, "asset_class": "Classe"}
    positions = PortfolioLoader(path, "Portfolio", column_map).load()
    assert positions[0].asset_class == "Equity"


def test_skips_rows_with_zero_or_blank_position_value(tmp_path):
    # Linhas de referência/watchlist (sem posição de fato) não devem virar
    # chamadas de histórico na Bloomberg -- contribuiriam zero pro P&L de
    # qualquer forma.
    path = _write_xlsx(
        tmp_path,
        [
            {"Ativo": "Ação X", "Ticker": "X US Equity", "Tipo": "Notional", "Posicao": 1_000_000},
            {"Ativo": "Watchlist Y", "Ticker": "Y US Equity", "Tipo": "Notional", "Posicao": 0},
            {"Ativo": "Watchlist Z", "Ticker": "Z US Equity", "Tipo": "Notional", "Posicao": None},
        ],
    )
    positions = PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()
    assert len(positions) == 1
    assert positions[0].ticker == "X US Equity"


def test_skips_zero_position_row_even_with_garbage_tipo(tmp_path):
    # Linha de referência com "Tipo" preenchido de qualquer jeito (ou vazio)
    # não deve derrubar o load -- ela nem chega a ser validada, já que tem
    # posição zerada.
    path = _write_xlsx(
        tmp_path,
        [
            {"Ativo": "Ação X", "Ticker": "X US Equity", "Tipo": "Notional", "Posicao": 1_000_000},
            {"Ativo": "Watchlist Y", "Ticker": "Y US Equity", "Tipo": "???", "Posicao": 0},
        ],
    )
    positions = PortfolioLoader(path, "Portfolio", COLUMN_MAP).load()
    assert len(positions) == 1


def test_raises_helpful_error_when_configured_column_missing(tmp_path):
    path = _write_xlsx(
        tmp_path,
        [{"Ativo": "ES1", "Ticker": "ES1 Index", "Tipo": "Notional", "Posicao": 10_000_000}],
    )
    column_map = {**COLUMN_MAP, "position_value": "Posição não existe"}
    with pytest.raises(KeyError, match="não encontrada"):
        PortfolioLoader(path, "Portfolio", column_map).load()
