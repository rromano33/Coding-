"""Builds a scenario discount curve: the market's own meeting-dated path
(see central_banks/stripper.py) with some meetings shocked by extra bps.

A shock persists from the meeting it's attached to through every later
meeting, until a later shock in the same scenario replaces it — the
scenario represents a *view on the trajectory* ("Copom turns more hawkish
from meeting 3 onward"), not a one-off blip. Beyond the last modeled
meeting, the curve reverts to the base curve's own forward shape, shifted
by a constant offset equal to whatever shock is still in effect — so
long-dated vertices keep the market's shape instead of being pinned flat.
"""
from __future__ import annotations

from datetime import date

from emrates.conventions.compounding import discount_factor as _df_from_rate
from emrates.conventions.compounding import forward_rate as _extract_forward_rate
from emrates.conventions.compounding import zero_rate as _extract_zero_rate
from emrates.curves.base import DiscountCurve
from emrates.scenarios.model import Scenario


class ScenarioCurve:
    """Read-only interface matches DiscountCurve (valuation_date, tau,
    discount_factor, zero_rate, forward_rate) so it's a drop-in wherever a
    DiscountCurve is used for reporting — see scenarios/report.py."""

    def __init__(self, base_curve: DiscountCurve, boundary_dates: list[date], levels: list[float]):
        self.base_curve = base_curve
        self.valuation_date = base_curve.valuation_date
        self.convention = base_curve.convention
        self.compounding = base_curve.compounding
        self.calendar = base_curve.calendar
        self._boundary_dates = boundary_dates
        self._levels = levels  # levels[0] unused; levels[i] = rate over (boundary[i-1], boundary[i]]
        self._final_shift = levels[-1] - base_curve.forward_rate(boundary_dates[-2], boundary_dates[-1])
        self._dfs = self._chain_discount_factors()

    def tau(self, start: date, end: date) -> float:
        return self.base_curve.tau(start, end)

    def _chain_discount_factors(self) -> list[float]:
        dfs = [1.0]
        for i in range(1, len(self._boundary_dates)):
            tau = self.tau(self._boundary_dates[i - 1], self._boundary_dates[i])
            dfs.append(dfs[-1] * _df_from_rate(self._levels[i], tau, self.compounding))
        return dfs

    def _segment_index(self, d: date) -> int:
        for i in range(1, len(self._boundary_dates)):
            if d <= self._boundary_dates[i]:
                return i
        raise AssertionError("caller must check d <= last boundary date before calling")

    def discount_factor(self, d: date) -> float:
        if d == self.valuation_date:
            return 1.0
        last_boundary = self._boundary_dates[-1]
        if d <= last_boundary:
            i = self._segment_index(d)
            tau = self.tau(self._boundary_dates[i - 1], d)
            return self._dfs[i - 1] * _df_from_rate(self._levels[i], tau, self.compounding)
        # Beyond the modeled horizon: base curve's own forward shape from
        # here on, shifted by whatever shock is still in effect.
        tau_tail = self.tau(last_boundary, d)
        base_tail_rate = self.base_curve.forward_rate(last_boundary, d)
        return self._dfs[-1] * _df_from_rate(base_tail_rate + self._final_shift, tau_tail, self.compounding)

    def zero_rate(self, d: date) -> float:
        tau = self.tau(self.valuation_date, d)
        return _extract_zero_rate(self.discount_factor(d), tau, self.compounding)

    def forward_rate(self, start: date, end: date) -> float:
        tau = self.tau(start, end)
        return _extract_forward_rate(self.discount_factor(start), self.discount_factor(end), tau, self.compounding)


def build_scenario_curve(curve: DiscountCurve, meeting_dates: list[date], scenario: Scenario) -> ScenarioCurve:
    meeting_dates = sorted(meeting_dates)
    if len(meeting_dates) < 2:
        raise ValueError("build_scenario_curve precisa de pelo menos 2 datas de reunião (mesma regra do stripper)")
    boundary_dates = [curve.valuation_date] + meeting_dates

    shocks_by_date = {s.meeting_date: s.shock_bps / 1e4 for s in scenario.shocks}
    unknown = shocks_by_date.keys() - set(meeting_dates)
    if unknown:
        raise ValueError(
            f"cenário '{scenario.name}' tem choque em reunião fora do horizonte modelado: {sorted(unknown)}"
        )

    # levels[i] is the rate for the segment *ending* at boundary_dates[i]
    # (see class docstring), i.e. the segment BEFORE that meeting's decision
    # — so a shock declared at boundary_dates[i] must only start applying
    # to levels[i + 1] onward, never to levels[i] itself.
    levels = [0.0] * len(boundary_dates)
    cumulative_shock = 0.0
    for i in range(1, len(boundary_dates)):
        base_level = curve.forward_rate(boundary_dates[i - 1], boundary_dates[i])
        levels[i] = base_level + cumulative_shock
        cumulative_shock += shocks_by_date.get(boundary_dates[i], 0.0)

    return ScenarioCurve(curve, boundary_dates, levels)
