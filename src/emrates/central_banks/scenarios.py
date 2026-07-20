"""'What if the BC does X' scenario engine — full policy-path repricing.

You specify a shock (in bps) at one or more meeting dates. Each shock is
treated as a persistent shift to the implied path from that meeting
forward (until a later shock overrides it) — pass shocks at every meeting
you want to move explicitly if you don't want that persistence. The
resulting hypothetical discount curve is then a normal DiscountCurve, so
any swap position can be repriced on it with pricing/pnl.py to get
scenario PnL vertex by vertex.

Beyond the last meeting date supplied, the scenario curve carries forward
the ORIGINAL curve's shape, scaled by the cumulative shift applied at the
last meeting — i.e. the long end moves with the front, but its forward
shape past the BC horizon is left untouched.
"""
from __future__ import annotations

from datetime import date

from emrates.curves.base import DiscountCurve
from emrates.conventions.compounding import discount_factor as _df_from_rate


def shocked_levels(
    curve: DiscountCurve,
    meeting_dates: list[date],
    shocks_bps: dict[date, float],
) -> list[float]:
    """Returns one implied level per inter-meeting period (same indexing as
    stripper.strip_meeting_path's internal `levels`), with shocks applied
    persistently from their meeting date forward."""
    meeting_dates = sorted(meeting_dates)
    boundary_dates = [curve.valuation_date] + meeting_dates
    base_levels = [
        curve.forward_rate(boundary_dates[i], boundary_dates[i + 1]) for i in range(len(boundary_dates) - 1)
    ]

    out = list(base_levels)
    cumulative_shift = 0.0
    for i, meeting in enumerate(meeting_dates):
        if meeting in shocks_bps:
            cumulative_shift += shocks_bps[meeting] / 1e4
        out[i] += cumulative_shift
    return out


def build_scenario_curve(
    curve: DiscountCurve,
    meeting_dates: list[date],
    shocks_bps: dict[date, float],
) -> DiscountCurve:
    meeting_dates = sorted(meeting_dates)
    levels = shocked_levels(curve, meeting_dates, shocks_bps)
    boundary_dates = [curve.valuation_date] + meeting_dates

    dfs = [1.0]
    for i, level in enumerate(levels):
        tau = curve.tau(boundary_dates[i], boundary_dates[i + 1])
        dfs.append(dfs[-1] * _df_from_rate(level, tau, curve.compounding))

    last_meeting = meeting_dates[-1]
    df_scenario_at_horizon = dfs[-1]
    df_original_at_horizon = curve.discount_factor(last_meeting)
    carry_factor = df_scenario_at_horizon / df_original_at_horizon

    far_dates = [d for d in curve.pillar_dates if d > last_meeting]
    far_dfs = [carry_factor * curve.discount_factor(d) for d in far_dates]

    return DiscountCurve(
        curve.valuation_date,
        meeting_dates + far_dates,
        dfs[1:] + far_dfs,
        curve.convention,
        curve.compounding,
        curve.calendar,
    )
