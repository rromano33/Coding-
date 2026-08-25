"""Confere que config/fx_strategy.example.yaml (o template versionado,
copiado pra config/fx_strategy.yaml -- pessoal, gitignored) tem a
estrutura que fxstrategy/carry.py espera, e que as escalas/tenores
declarados no YAML batem com as constantes confirmadas no terminal
(FWD_POINTS_SCALE/TENOR_DAYS) -- pra pegar deriva se um dos dois lados
mudar sem o outro."""
from pathlib import Path

import pytest
import yaml

from fxstrategy.carry import FWD_POINTS_SCALE, TENOR_DAYS, CarryLeg

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "fx_strategy.example.yaml"


@pytest.fixture
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_config_has_expected_top_level_keys(config):
    for key in ("paths", "price_history", "trend_pairs", "carry_legs", "funding_currencies", "carry_tenor"):
        assert key in config


def test_config_carry_legs_cover_every_currency_with_a_scale(config):
    assert set(config["carry_legs"].keys()) == set(FWD_POINTS_SCALE.keys())
    for currency, leg_cfg in config["carry_legs"].items():
        assert leg_cfg["scale"] == FWD_POINTS_SCALE[currency]


def test_config_carry_tenor_is_a_valid_tenor_days_key(config):
    assert config["carry_tenor"] in TENOR_DAYS


def test_config_funding_currencies_are_usd_or_a_configured_carry_leg(config):
    for funding in config["funding_currencies"]:
        assert funding == "USD" or funding in config["carry_legs"]


def test_config_carry_legs_build_valid_carry_leg_objects(config):
    tenor_label = config["carry_tenor"]
    for currency, leg_cfg in config["carry_legs"].items():
        leg = CarryLeg(
            currency=currency,
            spot_ticker=leg_cfg["spot_ticker"],
            points_ticker=leg_cfg[f"points_ticker_{tenor_label.lower()}"],
            scale=leg_cfg["scale"],
            tenor_days=TENOR_DAYS[tenor_label],
        )
        assert leg.spot_ticker.endswith("Curncy")
        assert leg.points_ticker.endswith("Curncy")
