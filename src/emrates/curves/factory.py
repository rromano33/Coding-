"""Reads config/countries/<country>.yaml and builds the right CurveBuilder."""
from __future__ import annotations

from pathlib import Path

import yaml

from emrates.conventions.compounding import Compounding
from emrates.conventions.daycount import DayCount
from emrates.curves.base import HybridCurveBuilder, ParSwapCurveBuilder, ZeroRateCurveBuilder
from emrates.data.calendars import Calendar


def load_country_config(country: str, config_dir: str | Path = "config/countries") -> dict:
    path = Path(config_dir) / f"{country}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_curve_builder(country_config: dict, calendar: Calendar | None = None):
    convention = DayCount(country_config["day_count"].replace("ACT/365F", "ACT/365"))
    compounding = Compounding(country_config["compounding"])

    if country_config["pillar_type"] == "zero_rate":
        return ZeroRateCurveBuilder(convention, compounding, calendar)
    if country_config["pillar_type"] == "par_swap":
        return ParSwapCurveBuilder(
            convention, compounding, country_config["coupon_frequency_months"], calendar
        )
    if country_config["pillar_type"] == "hybrid_bullet_then_coupon":
        return HybridCurveBuilder(
            convention,
            compounding,
            country_config["coupon_frequency_months"],
            country_config["bullet_cutoff_months"],
            calendar,
        )
    raise ValueError(f"unknown pillar_type: {country_config['pillar_type']}")
