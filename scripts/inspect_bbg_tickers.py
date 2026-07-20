"""Roda localmente (Bloomberg Terminal ativo). Para cada ticker "Curve" da
aba Tickers, puxa um conjunto de campos de referência candidatos a
determinar o vencimento do instrumento — MATURITY e LAST_TRADEABLE_DT
para instrumentos com data fixa (futuros, títulos), TENOR para pontos de
curva genéricos/constant-maturity — junto com SECURITY_DES e
SECURITY_TYP2 para eu entender o tipo de cada instrumento.

Cola o resultado de volta: com isso decido, por país, se dá pra usar o
campo de vencimento direto da Bloomberg (mais robusto) ou se precisa de
outra lógica.

Usage: python scripts/inspect_bbg_tickers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.data.bbg_client import BbgClient
from emrates.data.excel_loader import InputsBCsLoader

FIELDS = ["SECURITY_DES", "SECURITY_TYP2", "MATURITY", "LAST_TRADEABLE_DT", "TENOR", "CRNCY"]


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
    curve_tickers = [t for t in tickers if t.kind.lower() == "curve"]

    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    by_country: dict[str, list[str]] = {}
    for t in curve_tickers:
        by_country.setdefault(t.country, []).append(t.ticker)

    for country, country_tickers in by_country.items():
        print(f"\n=== {country} ({len(country_tickers)} tickers) ===")
        df = bbg.reference_fields(country_tickers, FIELDS)
        print(df.to_string())


if __name__ == "__main__":
    main()
