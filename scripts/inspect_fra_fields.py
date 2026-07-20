"""Roda localmente (Bloomberg Terminal ativo). Puxa um conjunto amplo de
campos candidatos para os tickers de FRA (CKFR.../PZFR.../HFFR...) — como
MATURITY e LAST_TRADEABLE_DT vieram vazios para eles, preciso descobrir
qual campo carrega a data de início/fim do período do FRA antes de tentar
decodificar isso a partir do próprio texto do ticker (arriscado: um FRA
mal interpretado corrompe a ponta curta da curva inteira).

Usage: python scripts/inspect_fra_fields.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.data.bbg_client import BbgClient
from emrates.data.excel_loader import InputsBCsLoader

FIELDS = [
    "SECURITY_DES",
    "NAME",
    "LONG_COMP_NAME",
    "SETTLE_DT",
    "START_ACCRUAL_DT",
    "END_ACCRUAL_DT",
    "FLT_START_DT",
    "FLT_END_DT",
    "FWD_START_DATE",
    "FWD_END_DATE",
    "FUT_DLV_DT_FIRST",
    "FUT_DLV_DT_LAST",
    "FIRST_SETTLE_DT",
]

FRA_COUNTRIES_PREFIX = {"czech": "CKFR", "poland": "PZFR", "hungary": "HFFR"}


def main() -> None:
    settings = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))
    column_map = {
        "tickers": settings["tickers_columns"],
        "tickers_sheet": settings["sheets"]["tickers_sheet"],
        "dates": settings["dates_columns"],
        "dates_sheet": settings["sheets"]["dates_sheet"],
        "positions": settings["positions_columns"],
        "positions_sheet": settings["sheets"]["positions_sheet"],
    }
    loader = InputsBCsLoader(settings["paths"]["inputs_bcs"], column_map)
    tickers = loader.load_tickers()

    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    for country, prefix in FRA_COUNTRIES_PREFIX.items():
        fra_tickers = [
            t.ticker
            for t in tickers
            if t.country.strip().lower().replace(" ", "_") == country and t.ticker.upper().startswith(prefix)
        ]
        if not fra_tickers:
            print(f"\n=== {country}: nenhum ticker FRA encontrado (prefixo {prefix}) ===")
            continue
        print(f"\n=== {country} ({len(fra_tickers)} FRAs) ===")
        df = bbg.reference_fields(fra_tickers, FIELDS)
        print(df.to_string())


if __name__ == "__main__":
    main()
