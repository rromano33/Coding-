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
market_forward_pct/market_zero_pct columns against the user's typed path
gives for free, without needing a second "shock" concept in the browser.
"""
from __future__ import annotations

from datetime import date

from emrates.curves.base import DiscountCurve


def build_lab_skeleton(curve: DiscountCurve, meetings: list[date], current_policy_rate: float) -> dict:
    meetings = sorted(meetings)
    if not meetings:
        raise ValueError("build_lab_skeleton precisa de pelo menos 1 reunião")
    boundary_dates = [curve.valuation_date] + meetings

    meeting_skeleton = []
    for i in range(1, len(boundary_dates)):
        meeting_skeleton.append(
            {
                "date": boundary_dates[i].isoformat(),
                "tau": curve.tau(boundary_dates[i - 1], boundary_dates[i]),
                "market_forward_pct": curve.forward_rate(boundary_dates[i - 1], boundary_dates[i]) * 100,
            }
        )

    last_boundary = boundary_dates[-1]
    vertex_skeleton = []
    for maturity in curve.pillar_dates:
        entry = {
            "maturity": maturity.isoformat(),
            "tau_from_valuation": curve.tau(curve.valuation_date, maturity),
            "market_zero_pct": curve.zero_rate(maturity) * 100,
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
