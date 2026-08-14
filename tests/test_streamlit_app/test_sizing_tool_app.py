"""Smoke test do app Streamlit via streamlit.testing.v1.AppTest -- roda o
script de verdade (sem navegador) contra uma planilha sintética e confere
que ele renderiza sem exceção e mostra números plausíveis. Não substitui
os testes de riskvar/sizing.py (esses cobrem a matemática em detalhe);
aqui o objetivo é só pegar erros de wiring da UI (nome de widget errado,
import quebrado, KeyError de config) que só aparecem rodando o app de
verdade."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import streamlit as st
import yaml
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[2] / "streamlit_app" / "sizing_tool.py")


@pytest.fixture(autouse=True)
def _clear_streamlit_cache():
    # st.cache_data é um registro global do processo, keyed pela função
    # (não pelos argumentos -- _load_price_histories() não recebe
    # nenhum) -- sem isso, o resultado da PRIMEIRA planilha sintética
    # carregada num teste vaza pros testes seguintes mesmo com
    # PORTFOLIO_RISK_CONFIG apontando pra outro arquivo.
    st.cache_data.clear()
    yield
    st.cache_data.clear()


@pytest.fixture
def fixture_config(tmp_path: Path) -> Path:
    rng = np.random.default_rng(3)
    n = 800
    dates = pd.bdate_range(end="2026-08-07", periods=n)
    eurusd = 1.10 + np.cumsum(rng.normal(0, 0.003, n))
    di_rate = 10.0 + np.cumsum(rng.normal(0, 0.02, n))

    rows = [
        ["Start Date", dates[0].strftime("%d/%m/%y"), None],
        ["End Date", dates[-1].strftime("%d/%m/%y"), None],
        [None, None, None],
        ["Classe", "FX", "EM Rates"],
        ["Ativo", "EURUSD", "DI Jan28"],
        ["BBG", "EURUSD Curncy", "F28 Curncy"],
    ]
    for d, a, b in zip(dates, eurusd, di_rate):
        rows.append([d, a, b])
    df = pd.DataFrame(rows)

    xlsx_path = tmp_path / "Portfolio.xlsx"
    with pd.ExcelWriter(xlsx_path) as writer:
        df.to_excel(writer, sheet_name="Preços", header=False, index=False)

    config = {
        "paths": {"portfolio_xlsx": str(xlsx_path), "output_dir": str(tmp_path)},
        "sheet": "Summary",
        "columns": {"asset": "Ativo", "ticker": "BBG", "position_type": "Tipo", "position_value": "Posição"},
        "price_history": {"sheet": "Preços", "ticker_row_label": "BBG"},
        "lookback_windows": {"3M": 63, "12M": 252},
        "confidence_levels": [0.95, 0.99],
        "trading_days_per_year": 252,
        "base_currency": "USD",
    }
    config_path = tmp_path / "portfolio_risk.yaml"
    config_path.write_text(yaml.dump(config))
    return config_path


def test_sizing_tool_app_renders_without_exception(fixture_config, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_RISK_CONFIG", str(fixture_config))
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception


def test_sizing_tool_app_shows_metrics_for_default_ticker(fixture_config, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_RISK_CONFIG", str(fixture_config))
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception

    metric_labels = [m.label for m in at.metric]
    assert any("Notional" in label or "DV01" in label for label in metric_labels)
    assert any("1σ diário" in label for label in metric_labels)
    assert any("Preço de stop" in label for label in metric_labels)


def test_sizing_tool_app_missing_config_shows_friendly_error_not_traceback(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_RISK_CONFIG", str(tmp_path / "does_not_exist.yaml"))
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=30)
    assert not at.exception
    assert any("não encontrei" in e.value.lower() or "não consegui" in e.value.lower() for e in at.error)
