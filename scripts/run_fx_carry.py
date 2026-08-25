"""Lê a aba "Preços FX" da planilha (config/fx_strategy.yaml) e calcula o
carry atual (anualizado, via forward points) de cada moeda EM configurada
em `carry_legs`, financiada em cada moeda de `funding_currencies` -- ver
fxstrategy/carry.py pra fórmula e convenção de sinal.

Não depende de sessão Bloomberg em Python (BBComm/xbbg) -- o histórico
vem pronto da aba "Preços FX" da própria planilha, preenchida no Excel via
=BDH(...). Mesmo mecanismo de riskvar/price_history.py.

Escopo atual: só a perna de carry (checagem de que os dados/fórmula batem
com o esperado antes de ir pra sinal/backtest/sizing). Trend ainda não
está implementado.

python scripts/run_fx_carry.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fxstrategy.carry import TENOR_DAYS, CarryLeg, carry_series
from riskvar.price_history import load_price_history

CONFIG_PATH = Path("config/fx_strategy.yaml")
EXAMPLE_CONFIG_PATH = Path("config/fx_strategy.example.yaml")


def build_carry_leg(leg_cfg: dict, currency: str, tenor_label: str) -> CarryLeg:
    return CarryLeg(
        currency=currency,
        spot_ticker=leg_cfg["spot_ticker"],
        points_ticker=leg_cfg[f"points_ticker_{tenor_label.lower()}"],
        scale=leg_cfg["scale"],
        tenor_days=TENOR_DAYS[tenor_label],
    )


def main() -> None:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"\n{CONFIG_PATH} não existe ainda -- esse arquivo é pessoal (não vem no git).\n\n"
            f"Primeira vez rodando isso? Copie o template e edite se precisar:\n"
            f"  cp {EXAMPLE_CONFIG_PATH} {CONFIG_PATH}\n"
        )
    settings = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    price_history_cfg = settings["price_history"]
    price_histories = load_price_history(
        settings["paths"]["portfolio_xlsx"],
        price_history_cfg["sheet"],
        price_history_cfg.get("ticker_row_label", "BBG"),
    )
    print(f"{len(price_histories)} tickers com histórico carregados de {settings['paths']['portfolio_xlsx']} "
          f"(aba {price_history_cfg['sheet']!r})")

    tenor_label = settings["carry_tenor"]
    carry_legs_cfg = settings["carry_legs"]
    funding_currencies = settings["funding_currencies"]
    em_currencies = [c for c in carry_legs_cfg if c not in funding_currencies]

    if not em_currencies:
        raise SystemExit(
            f"Nenhuma moeda EM sobrou depois de excluir funding_currencies={funding_currencies} "
            f"de carry_legs={list(carry_legs_cfg)} -- confira o config."
        )

    rows = []
    for em_currency in em_currencies:
        em_leg = build_carry_leg(carry_legs_cfg[em_currency], em_currency, tenor_label)
        for funding in funding_currencies:
            funding_leg = None if funding == "USD" else build_carry_leg(carry_legs_cfg[funding], funding, tenor_label)
            try:
                series = carry_series(price_histories, em_leg, funding_leg)
            except KeyError as e:
                print(f"\n{em_currency} financiado em {funding}: pulado -- {e}")
                continue
            if series.empty:
                print(f"\n{em_currency} financiado em {funding}: pulado -- sem datas em comum entre as pernas.")
                continue
            rows.append({
                "em": em_currency,
                "financiado_em": funding,
                "tenor": tenor_label,
                "carry_atual_pct": series.iloc[-1] * 100.0,
                "carry_medio_60d_pct": series.tail(60).mean() * 100.0,
                "carry_medio_full_pct": series.mean() * 100.0,
                "n_obs": len(series),
                "ultima_data": series.index[-1].date(),
            })

    if not rows:
        raise SystemExit("Nenhuma perna de carry calculada -- confira os tickers na aba de preços.")

    report = pd.DataFrame(rows).sort_values("carry_atual_pct", ascending=False)
    print()
    print(report.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    output_dir = Path(settings["paths"].get("output_dir", "Data/processed"))
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"fx_carry_{date.today()}.csv"
    report.to_csv(out_path, index=False)
    print(f"\nSalvo em {out_path}")


if __name__ == "__main__":
    main()
