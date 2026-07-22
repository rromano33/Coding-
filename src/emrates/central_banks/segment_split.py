"""Splits a single market-implied rate change across multiple real BC
meetings that share it.

Happens whenever the underlying market data (swap curve pillars, FRA
quotes) is sparser than the BC's own meeting calendar — e.g. Colombia's
swap curve goes annual beyond 18 months while Banrep meets ~8x/year, so a
single pillar-to-pillar segment can contain 5-6 real meetings with only
one number (that segment's own implied change) to describe all of them.

Rather than smoothing the change evenly across every meeting in the
segment (implying nothing happens until the SECOND-to-last decision) or
assuming it lands entirely on one meeting, this is an explicit, declared
assumption: the first meeting in the segment gets the majority of the
move (65% by default — central banks tend to move early once a segment's
belief shifts, not wait), and the rest of that segment's meetings split
what's left evenly.
"""
from __future__ import annotations


def split_segment_change(total_change_bps: float, n_meetings: int, first_weight: float = 0.65) -> list[float]:
    if n_meetings <= 0:
        return []
    if n_meetings == 1:
        return [total_change_bps]
    remaining_weight = (1.0 - first_weight) / (n_meetings - 1)
    return [total_change_bps * first_weight] + [total_change_bps * remaining_weight] * (n_meetings - 1)
