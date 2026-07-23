from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from riskvar.price_history import load_price_history


def _write_precos_xlsx(tmp_path: Path) -> Path:
    # Reproduz o layout real: rótulos na coluna A (Start Date/End Date/
    # linha em branco/Classe/Ativo/BBG), depois uma linha por data (célula
    # de data de verdade, como o Excel guarda -- só a formatação de exibição
    # é "01/jan/19", o valor por baixo é um serial de data normal). Algumas
    # células vêm como o erro nativo do Excel/Bloomberg "#N/A N/A" quando
    # não há cotação naquele dia (feriado, ativo ainda não existia etc).
    rows = [
        ["Start Date", "01/01/2019", None],
        ["End Date", "23/07/2026", None],
        [None, None, None],
        ["Classe", "Equity", "DM Rates"],
        ["Ativo", "ES1", "SFRZ7"],
        ["BBG", "ES1 Index", "SFRZ7 Comdty"],
        [date(2019, 1, 1), 2505.25, "#N/A N/A"],
        [date(2019, 1, 2), 2511.00, "#N/A N/A"],
        [date(2019, 1, 3), 2447.75, 97.5],
    ]
    df = pd.DataFrame(rows)
    path = tmp_path / "portfolio.xlsx"
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Preços", header=False, index=False)
    return path


def test_load_price_history_parses_series_per_ticker(tmp_path):
    path = _write_precos_xlsx(tmp_path)
    histories = load_price_history(path, "Preços")

    assert set(histories.keys()) == {"ES1 Index", "SFRZ7 Comdty"}
    assert len(histories["ES1 Index"]) == 3
    assert histories["ES1 Index"].iloc[0] == pytest.approx(2505.25)


def test_load_price_history_drops_na_error_cells(tmp_path):
    path = _write_precos_xlsx(tmp_path)
    histories = load_price_history(path, "Preços")

    # SFRZ7 só tem cotação real no 3º dia -- os dois primeiros são "#N/A N/A"
    assert len(histories["SFRZ7 Comdty"]) == 1
    assert histories["SFRZ7 Comdty"].iloc[0] == pytest.approx(97.5)


def test_load_price_history_sorts_by_date_ascending(tmp_path):
    path = _write_precos_xlsx(tmp_path)
    histories = load_price_history(path, "Preços")
    dates = histories["ES1 Index"].index
    assert list(dates) == sorted(dates)


def test_load_price_history_raises_helpful_error_when_ticker_row_missing(tmp_path):
    df = pd.DataFrame([["Something else", "x"]])
    path = tmp_path / "bad.xlsx"
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Preços", header=False, index=False)

    with pytest.raises(KeyError, match="não encontrada"):
        load_price_history(path, "Preços")
