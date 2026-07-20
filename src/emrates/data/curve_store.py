"""Persists/reloads DiscountCurve snapshots so run_pnl.py can diff today vs
yesterday without needing yesterday's raw Bloomberg prices again."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import DiscountCurve
from emrates.data.calendars import Calendar


def save_curve(curve: DiscountCurve, out_dir: str | Path, country: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"curve_{country}_{curve.valuation_date}.json"
    payload = {
        "valuation_date": curve.valuation_date.isoformat(),
        "pillar_dates": [d.isoformat() for d in curve.pillar_dates],
        "discount_factors": curve.discount_factors,
        "convention": curve.convention.value,
        "compounding": curve.compounding.value,
    }
    path.write_text(json.dumps(payload))
    return path


def load_curve(path: str | Path, calendar: Calendar | None = None) -> DiscountCurve:
    payload = json.loads(Path(path).read_text())
    return DiscountCurve(
        date.fromisoformat(payload["valuation_date"]),
        [date.fromisoformat(d) for d in payload["pillar_dates"]],
        payload["discount_factors"],
        DayCount(payload["convention"]),
        Compounding(payload["compounding"]),
        calendar,
    )


def latest_curve_before(out_dir: str | Path, country: str, before: date) -> Path | None:
    out_dir = Path(out_dir)
    candidates = sorted(out_dir.glob(f"curve_{country}_*.json"))
    prior = [p for p in candidates if date.fromisoformat(p.stem.split("_")[-1]) < before]
    return prior[-1] if prior else None
