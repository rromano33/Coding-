"""A scenario: a named set of extra bps shocks on top of what's already
priced by the market for specific BC meetings — stored as a small YAML file
so scenarios can be authored/edited without touching code. See
scenarios/brazil/ for examples.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Shock:
    meeting_date: date
    # Additive to the rate level *after* that meeting, in bps. Positive =
    # more hawkish (higher rate) than what the market already has priced;
    # negative = more dovish (more cutting). Persists to later meetings
    # until a later shock in the same scenario replaces it.
    shock_bps: float


@dataclass(frozen=True)
class Scenario:
    name: str
    country: str
    shocks: list[Shock]


def load_scenario(path: str | Path) -> Scenario:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    shocks = [
        Shock(meeting_date=_parse_date(s["meeting_date"]), shock_bps=float(s["shock_bps"]))
        for s in payload.get("shocks", [])
    ]
    return Scenario(name=payload["name"], country=payload["country"], shocks=shocks)


def _parse_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))
