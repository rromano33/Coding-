"""Curva de interpolação linear direta na taxa cotada de cada pilar -- sem
bootstrap de cupom, sem interpolação cúbica -- usada SÓ no relatório
priced_bc do México (Ricardo, 29/07/2026).

Contexto: Ricardo comparou nosso "quanto está precificado por reunião" pro
México contra a curva de TIIE que ele monta no Bloomberg (mesmos tickers
MPSW, mesmas taxas) e viu uma diferença crescente com o prazo -- ~26bps
acumulados até dez/27 usando NSS, e pior ainda (~55bps) com o split 65/35
que já usamos pra Colômbia. Testado numericamente contra os tickers/taxas
reais da planilha dele: tratar cada cotação de swap como uma taxa zero
direta (sem bootstrap de cupom) e interpolar linearmente entre pilares
(não com a cúbica monótona de DiscountCurve, nem com o ajuste NSS) chegou
MUITO mais perto da referência dele -- diferença final caiu pra ~13.6bps
(a maior parte do resíduo não explicada; capitalização linear e day count
ACT/365 foram testados e pioraram ou não mudaram nada, então a combinação
aqui -- day count/capitalização do próprio config do país -- é a melhor
encontrada até agora).

IMPORTANTE -- essa curva NÃO substitui a curva usada pra precificar
posições/PnL (ParSwapCurveBuilder, bootstrap de cupom + interpolação
cúbica de DiscountCurve continuam exatamente como antes). Ricardo pediu
explicitamente pra mudar só o relatório de reuniões, não o motor de
pricing inteiro -- trocar as duas seria uma mudança consequente pra PnL
real de posições, que ele preferiu não fazer agora."""
from __future__ import annotations

from datetime import date

from emrates.conventions.compounding import Compounding, discount_factor, forward_rate
from emrates.conventions.daycount import DayCount, year_fraction
from emrates.curves.base import Pillar
from emrates.data.calendars import Calendar


class LinearRateCurve:
    """Drop-in pra central_banks/stripper.py (valuation_date/tau/forward_rate)
    -- não é uma DiscountCurve completa, não serve pra valuation de swap."""

    def __init__(
        self,
        valuation_date: date,
        taus: list[float],
        rates: list[float],
        convention: DayCount,
        compounding: Compounding,
        calendar: Calendar | None,
    ):
        self.valuation_date = valuation_date
        self._taus = taus
        self._rates = rates
        self.convention = convention
        self.compounding = compounding
        self.calendar = calendar

    def tau(self, start: date, end: date) -> float:
        return year_fraction(start, end, self.convention, self.calendar)

    def _zero_rate(self, t: float) -> float:
        taus, rates = self._taus, self._rates
        if t <= taus[0]:
            return rates[0]
        if t >= taus[-1]:
            return rates[-1]
        for i in range(1, len(taus)):
            if t <= taus[i]:
                weight = (t - taus[i - 1]) / (taus[i] - taus[i - 1])
                return rates[i - 1] + weight * (rates[i] - rates[i - 1])
        return rates[-1]  # pragma: no cover -- inatingível dado o clamp acima

    def discount_factor(self, d: date) -> float:
        if d == self.valuation_date:
            return 1.0
        t = self.tau(self.valuation_date, d)
        return discount_factor(self._zero_rate(t), t, self.compounding)

    def forward_rate(self, start: date, end: date) -> float:
        tau = self.tau(start, end)
        df_start, df_end = self.discount_factor(start), self.discount_factor(end)
        return forward_rate(df_start, df_end, tau, self.compounding)


def build_linear_rate_curve(
    valuation_date: date,
    pillars: list[Pillar],
    convention: DayCount,
    compounding: Compounding,
    calendar: Calendar | None,
) -> LinearRateCurve:
    if not pillars:
        raise ValueError("build_linear_rate_curve precisa de pelo menos 1 pilar")
    pillars = sorted(pillars, key=lambda p: p.maturity)
    taus = [year_fraction(valuation_date, p.maturity, convention, calendar) for p in pillars]
    rates = [p.rate for p in pillars]
    return LinearRateCurve(valuation_date, taus, rates, convention, compounding, calendar)
