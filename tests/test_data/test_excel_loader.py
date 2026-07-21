from datetime import date

import pandas as pd

from emrates.data.excel_loader import InputsBCsLoader

COLUMN_MAP = {
    "tickers": {"country": "Country", "kind": "Type", "description": "Description", "ticker": "Ticker"},
    "tickers_sheet": "Tickers",
    "dates": {
        "meetings": {"BCB": "brazil"},
        "holidays": {"Feriados_Brazil": "brazil", "Feriados_Banrep": "colombia", "Feriados_south_africa": "south_africa"},
    },
    "dates_sheet": "Dates",
    "positions": {"TradeID": "TradeID"},
    "positions_sheet": "Posições",
}


def _write_workbook(path, dates_df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"Ticker": [], "Country": [], "Description": [], "Type": []}).to_excel(
            writer, sheet_name="Tickers", index=False
        )
        dates_df.to_excel(writer, sheet_name="Dates", index=False)
        pd.DataFrame({"TradeID": []}).to_excel(writer, sheet_name="Posições", index=False)


def test_holiday_columns_match_regardless_of_case(tmp_path):
    # Real sheet mixes casing: 'Feriados_Brazil' (capital B) vs the
    # lowercase style used elsewhere ('feriados_south_africa' here, to
    # prove a case mismatch against config's 'Feriados_south_africa'
    # doesn't silently drop the country).
    path = tmp_path / "Input_BCs.xlsx"
    dates_df = pd.DataFrame(
        {
            "BCB": pd.to_datetime([date(2026, 8, 6)]),
            "feriados_brazil": pd.to_datetime([date(2026, 9, 7)]),
            "FERIADOS_BANREP": pd.to_datetime([date(2026, 1, 1)]),
            "feriados_south_africa": pd.to_datetime([date(2026, 4, 27)]),
        }
    )
    _write_workbook(path, dates_df)

    loader = InputsBCsLoader(path, COLUMN_MAP)
    holidays = loader.load_holidays()
    meetings = loader.load_meeting_dates()

    assert holidays["brazil"] == [date(2026, 9, 7)]
    assert holidays["colombia"] == [date(2026, 1, 1)]
    assert holidays["south_africa"] == [date(2026, 4, 27)]
    assert meetings["brazil"] == [date(2026, 8, 6)]


def test_missing_holiday_column_is_skipped_not_erroring(tmp_path):
    path = tmp_path / "Input_BCs.xlsx"
    dates_df = pd.DataFrame({"BCB": pd.to_datetime([date(2026, 8, 6)])})
    _write_workbook(path, dates_df)

    loader = InputsBCsLoader(path, COLUMN_MAP)
    holidays = loader.load_holidays()

    assert "brazil" not in holidays
