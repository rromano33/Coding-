"""Sinal de carry via forward points -- não via diferencial de taxa curta,
por decisão explícita (forward points embutem prêmio de risco/liquidez que
a taxa pura não capta).

Convenção: os pares usados (USDJPY, USDBRL, USDMXN, USDZAR) cotam USD
sempre como base -- "quantos <CCY> por 1 USD". Isso deixa a conta
genérica: o prêmio a termo anualizado de qualquer uma dessas moedas
contra o USD aproxima (paridade de juros coberta, CIP) r_CCY - r_USD:

    premium(CCY) = (forward_points / scale) / spot * (365 / tenor_dias)

Prêmio positivo = CCY rende mais que USD (candidata a carry longo, ex:
BRL). Prêmio negativo = CCY rende menos que USD (candidata a moeda de
financiamento, ex: JPY).

Pra trocar a moeda de financiamento de USD pra qualquer outra Y (ex:
JPY), não precisa de um ticker EM/Y direto (raramente líquido/cotado --
EM quase sempre só cota contra USD). Como as duas pernas passam pelo
mesmo USD comum:

    r_EM - r_Y = (r_EM - r_USD) - (r_Y - r_USD)
    carry(EM financiado em Y) = premium(EM) - premium(Y)

Financiar em USD é o caso trivial: premium(USD) = 0, então
carry(EM/USD) = premium(EM).

Escala e tenor confirmados diretamente no terminal Bloomberg (DES de cada
ticker) -- não são uniformes entre moedas, ver FWD_POINTS_SCALE."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Forward Scale confirmado na tela DES de cada ticker (não é o mesmo pra
# todas as moedas -- JPY usa 2 casas, as outras três usam 4).
FWD_POINTS_SCALE = {
    "JPY": 100.0,
    "BRL": 10_000.0,
    "MXN": 10_000.0,
    "ZAR": 10_000.0,
}
TENOR_DAYS = {"1M": 30, "3M": 90}


def forward_premium(spot: pd.Series, points: pd.Series, scale: float, tenor_days: int) -> pd.Series:
    """Prêmio a termo anualizado, em decimal (0.05 = 5%/ano). `spot` e
    `points` precisam já estar alinhados por data (mesmo índice) -- ver
    align_carry_inputs."""
    return (points / scale) / spot * (365.0 / tenor_days)


def align_carry_inputs(spot: pd.Series, points: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Alinha spot e points por interseção de datas (dropna nos dois) --
    mesma convenção defensiva do resto do projeto (ver
    riskvar.stress.fit_factor_sensitivities): séries de fontes/tickers
    diferentes raramente têm exatamente o mesmo calendário de cotação."""
    frame = pd.DataFrame({"spot": spot, "points": points}).dropna()
    return frame["spot"], frame["points"]


@dataclass(frozen=True)
class CarryLeg:
    currency: str        # "BRL", "MXN", "ZAR", "JPY" etc -- só rótulo, não entra na conta
    spot_ticker: str      # ex: "USDBRL Curncy"
    points_ticker: str    # ex: "BCN3M Curncy"
    scale: float
    tenor_days: int


def leg_premium_series(price_histories: dict[str, pd.Series], leg: CarryLeg) -> pd.Series:
    """Série histórica do prêmio anualizado de UMA perna (CCY vs USD)."""
    missing = [t for t in (leg.spot_ticker, leg.points_ticker) if t not in price_histories]
    if missing:
        raise KeyError(f"ticker(s) sem histórico pra montar a perna {leg.currency!r}: {missing}")
    spot, points = align_carry_inputs(price_histories[leg.spot_ticker], price_histories[leg.points_ticker])
    return forward_premium(spot, points, leg.scale, leg.tenor_days)


def carry_series(
    price_histories: dict[str, pd.Series], em_leg: CarryLeg, funding_leg: CarryLeg | None = None
) -> pd.Series:
    """Carry anualizado de `em_leg` financiado em `funding_leg` (USD se
    None -- caso trivial, premium(USD)=0 então carry = premium(em_leg)).
    Alinha as duas séries de prêmio por interseção de datas antes de
    subtrair (podem ter calendários ligeiramente diferentes)."""
    em_premium = leg_premium_series(price_histories, em_leg)
    if funding_leg is None:
        return em_premium
    funding_premium = leg_premium_series(price_histories, funding_leg)
    frame = pd.DataFrame({"em": em_premium, "funding": funding_premium}).dropna()
    return frame["em"] - frame["funding"]
