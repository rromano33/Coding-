"""Builds a JSON-serializable "skeleton" of a country's curve + BC meeting
calendar so a browser can recompute an absolute rate-path scenario live,
with no server and no Python involved after the page loads -- this backs
the interactive "Cenários" tab in build_dashboard.py.

Design: everything that needs a calendar or day-count convention (year
fractions, which segment of the meeting timeline a curve vertex falls
into) is precomputed here in Python and baked into the page as plain
numbers. The browser only ever does simple compounding arithmetic
(conventions/compounding.py's three formulas, ported faithfully in JS --
see build_dashboard.py's LAB_SCRIPT) on top of those numbers plus
whatever bps the user typed for each meeting. It never needs to know
about BUS/252, modified-following, or how the base curve itself was
bootstrapped.

The scenario is an ABSOLUTE path (Ricardo, 29/07/2026): the user types the
actual bps move they think happens at each meeting, not a shock relative
to what the market already prices -- "surprise" only makes sense measured
against today's market, which is exactly what pairing this skeleton's
market_forward_pct against the user's typed path gives for free, without
needing a second "shock" concept in the browser.

IMPORTANT #1 (Ricardo, 29/07/2026 -- bug real, achado por print de tela): a
tabela inicial (heatmap/cards) e a tabela de cenários interativos "não
batiam", porque cada uma calculava o bps precificado por reunião do seu
próprio jeito -- os cards leem de priced_bc_<país>_<data>.csv, que dependendo
do país é produzido por um caminho totalmente diferente do curve.forward_rate
puro (curva suavizada por NSS, leitura direta de FRA, ou split 65/35 entre
reuniões de um mesmo segmento de pilar -- ver central_banks/stripper.py,
curves/fra_direct.py). Recalcular aqui via curve.forward_rate ignorava tudo
isso e usava a curva EXATA (não suavizada) por cima, produzindo um número
diferente (às vezes MUITO diferente -- ruído de interpolação entre pilares
esparsos). Por isso market_forward_pct/market_change_bps agora vêm como
parâmetro (direto do mesmo CSV que os cards leem), nunca recomputados aqui --
garante que as duas tabelas sempre saem exatamente da mesma base.

IMPORTANT #2 (Ricardo, 30/07/2026 -- segundo bug real, achado do mesmo
jeito): mesmo depois do fix acima, digitar EXATAMENTE o caminho que o "Mkt
Δbps" mostra como cenário não dava impacto zero nos vértices -- porque o
skeleton costumava expor um "market_zero_pct" por vértice calculado via
curve.zero_rate() na curva EXATA (a mesma usada pra precificar posições),
enquanto o caminho de reuniões (market_forward_pct/market_change_bps) vem
da curva do RELATÓRIO (NSS/linear-rate/split/FRA-direto conforme o país,
ver IMPORTANT #1) -- duas curvas diferentes, nunca batiam. A correção não
mexe em Python: o "market_zero_pct" por vértice foi removido do skeleton de
propósito, e o baseline de mercado passou a ser calculado no PRÓPRIO
navegador rodando o motor do cenário com o caminho de reuniões do mercado
como input (ver LAB_SCRIPT/computeLab em build_dashboard.py) -- isso
garante, por construção (mesma função determinística chamada duas vezes com
o mesmo input), que cenário == mercado sempre dá impacto zero.
"""
from __future__ import annotations

from datetime import date

from emrates.curves.base import DiscountCurve
from emrates.data.ticker_parsing import brazil_di1_label

_AVG_DAYS_PER_MONTH = 30.4368


def _tenor_label(valuation_date: date, maturity: date) -> str:
    """Rótulo genérico de tenor (3M, 18M, 2Y, 2Y6M, ...) pra países sem um
    código de contrato próprio -- Ricardo (29/07/2026) pediu um "nome" ao
    lado do vencimento na tabela de impacto por vértice, pra ficar mais
    fácil de reconhecer o vértice sem decorar a data exata."""
    months = round((maturity - valuation_date).days / _AVG_DAYS_PER_MONTH)
    if months <= 0:
        return "0M"
    if months < 12:
        return f"{months}M"
    years, rem_months = divmod(months, 12)
    return f"{years}Y" if rem_months == 0 else f"{years}Y{rem_months}M"


def _vertex_label(country: str, valuation_date: date, maturity: date) -> str:
    if country == "brazil":
        return brazil_di1_label(maturity)
    return _tenor_label(valuation_date, maturity)


def build_lab_skeleton(
    curve: DiscountCurve, meeting_reports: list[dict], current_policy_rate: float, country: str
) -> dict:
    """meeting_reports: uma linha por reunião, na MESMA fonte usada pelos
    cards/heatmap (priced_bc_<país>_<data>.csv) -- cada dict precisa ter
    "meeting_date" (date), "implied_change_bps" e "cumulative_change_from_spot_bps"
    (mesmos nomes de coluna do CSV). Não é recalculado a partir da curva aqui
    de propósito -- ver o docstring do módulo.

    country: usado só pra escolher o "nome" de cada vértice na tabela de
    impacto -- código de contrato DI1 (DIF27, DIN28, ...) pro Brasil,
    tenor aproximado (3M, 18M, 2Y, ...) pros demais países."""
    meeting_reports = sorted(meeting_reports, key=lambda m: m["meeting_date"])
    if not meeting_reports:
        raise ValueError("build_lab_skeleton precisa de pelo menos 1 reunião")
    meetings = [m["meeting_date"] for m in meeting_reports]
    boundary_dates = [curve.valuation_date] + meetings

    meeting_skeleton = []
    for i in range(1, len(boundary_dates)):
        r = meeting_reports[i - 1]
        meeting_skeleton.append(
            {
                "date": boundary_dates[i].isoformat(),
                "tau": curve.tau(boundary_dates[i - 1], boundary_dates[i]),
                # current_policy_rate + cumulative_change_from_spot_bps/100 é
                # a MESMA conta que a coluna "Acumulado" dos cards (bps ->
                # pontos percentuais) -- garante que os dois lugares mostrem
                # exatamente o mesmo número.
                "market_forward_pct": current_policy_rate * 100 + r["cumulative_change_from_spot_bps"] / 100,
                # O que o mercado já precifica NAQUELA reunião (não acumulado) --
                # mostrado ao lado do input pra comparar direto com o cenário
                # discreto que o usuário vai digitar (Ricardo, 29/07/2026).
                "market_change_bps": r["implied_change_bps"],
            }
        )

    last_boundary = boundary_dates[-1]
    vertex_skeleton = []
    for maturity in curve.pillar_dates:
        entry = {
            "maturity": maturity.isoformat(),
            "label": _vertex_label(country, curve.valuation_date, maturity),
            "tau_from_valuation": curve.tau(curve.valuation_date, maturity),
        }
        if maturity <= last_boundary:
            # 1-based index into `meetings`/boundary_dates -- the first
            # segment whose end is on/after this vertex's maturity.
            segment_index = next(i for i in range(1, len(boundary_dates)) if maturity <= boundary_dates[i])
            entry["segment_index"] = segment_index
            entry["tau_from_segment_start"] = curve.tau(boundary_dates[segment_index - 1], maturity)
        else:
            # Beyond the last modeled meeting: same tail convention as
            # ScenarioCurve.discount_factor -- the base curve's own forward
            # shape from there on, shifted by whatever the last meeting's
            # scenario level implies relative to the market's own forward
            # for that same last segment (computed client-side, since it
            # depends on the user's input).
            entry["segment_index"] = None
            entry["tail_tau"] = curve.tau(last_boundary, maturity)
            entry["tail_base_forward_pct"] = curve.forward_rate(last_boundary, maturity) * 100
        vertex_skeleton.append(entry)

    return {
        "valuation_date": curve.valuation_date.isoformat(),
        "compounding": curve.compounding.value,
        "current_policy_rate_pct": current_policy_rate * 100,
        "meetings": meeting_skeleton,
        "vertices": vertex_skeleton,
    }
