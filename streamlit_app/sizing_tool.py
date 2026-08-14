"""Vol-Adjusted Sizing Tool -- app Streamlit (roda LOCAL, não é gerado/
distribuído como os relatórios de riskvar/). Calcula o tamanho de posição
(Notional ou DV01) tal que, se o preço andar N desvios-padrão da variação
diária CONTRA a posição, a perda seja exatamente o "Max Loss" informado --
o stop se adapta ao regime de vol atual do ativo em vez de ser um % fixo
arbitrário.

Lê o histórico de preços/taxas do MESMO lugar que scripts/run_var.py e
scripts/build_interactive_var.py -- config/portfolio_risk.yaml
(paths.portfolio_xlsx + price_history.sheet/ticker_row_label), aba
"Preços" preenchida no Excel via =BDH(...) da Bloomberg. Não depende de
sessão Bloomberg em Python (BBComm/xbbg) -- mesmo motivo dos outros
scripts do projeto: essa sessão se mostrou instável.

A matemática (vol realizada, distância do stop, tamanho da posição) mora
em riskvar/sizing.py -- pure functions, testadas em
tests/test_riskvar/test_sizing.py, sem nada de Streamlit ali (só a
apresentação/UI depende do Streamlit, o cálculo não).

Rodar localmente:
    pip install -r requirements.txt
    streamlit run streamlit_app/sizing_tool.py
Abre automaticamente no navegador em http://localhost:8501 -- fecha o
terminal (Ctrl+C) pra parar o servidor.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riskvar.price_history import load_price_history
from riskvar.sizing import change_series, size_position, vol_stats, vol_stats_by_window

# Mesmo config/portfolio_risk.yaml pessoal usado por scripts/run_var.py e
# scripts/build_interactive_var.py -- PORTFOLIO_RISK_CONFIG só existe pra
# testar o app com uma planilha sintética (ver tests/test_streamlit_app/),
# nunca precisa ser setado no uso normal.
CONFIG_PATH = Path(os.environ.get("PORTFOLIO_RISK_CONFIG", str(Path(__file__).resolve().parents[1] / "config" / "portfolio_risk.yaml")))

VOL_WINDOW_OPTIONS = {
    "Últimos 6 meses": 126,
    "Último 1 ano": 252,
    "Últimos 2 anos": 504,
    "Últimos 3 anos": 756,
    "Todo o histórico": None,
}
ROLLING_TABLE_WINDOWS = {"7D": 7, "15D": 15, "30D": 30, "60D": 60}
ROLLING_CHART_WINDOWS = {"7D": 7, "15D": 15, "30D": 30, "60D": 60}

st.set_page_config(page_title="Sizing Tool", layout="wide")


@st.cache_data(show_spinner="Lendo histórico de preços da planilha...")
def _load_price_histories() -> dict[str, pd.Series]:
    if not CONFIG_PATH.exists():
        return {}
    settings = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg = settings["price_history"]
    return load_price_history(settings["paths"]["portfolio_xlsx"], cfg["sheet"], cfg.get("ticker_row_label", "BBG"))


def _price_chart(prices: pd.Series, trade_price: float, stop_price: float, target_price: float) -> go.Figure:
    recent = prices.tail(252)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent.index, y=recent.values, mode="lines", name="Preço", line=dict(color="#2a78d6", width=1.5)))
    for label, value, color in [("Entrada", trade_price, "#898781"), ("Stop", stop_price, "#d03b3b"), ("Alvo", target_price, "#006300")]:
        fig.add_hline(y=value, line=dict(color=color, width=1, dash="dot"), annotation_text=f"{label} {value:.4f}", annotation_position="right")
    fig.update_layout(title="Preço — últimos 12 meses", height=380, margin=dict(l=40, r=100, t=40, b=30), showlegend=False)
    return fig


def _return_distribution_chart(changes: pd.Series, unit_label: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=changes, nbinsx=40, marker=dict(color="#2a78d6")))
    fig.update_layout(title="Distribuição de variações diárias", xaxis_title=f"Variação diária ({unit_label})",
                       yaxis_title="Frequência (dias)", height=380, margin=dict(l=40, r=20, t=40, b=40))
    return fig


def _rolling_vol_chart(changes: pd.Series, windows: dict[str, int], trading_days_per_year: int) -> go.Figure:
    fig = go.Figure()
    for label, n_days in windows.items():
        rolling = changes.rolling(n_days).std() * (trading_days_per_year ** 0.5)
        fig.add_trace(go.Scatter(x=rolling.index, y=rolling.values, mode="lines", name=label))
    fig.update_layout(title="Vol realizada móvel (anualizada)", height=380, margin=dict(l=40, r=20, t=40, b=30),
                       legend=dict(orientation="h", y=1.12))
    return fig


def main() -> None:
    title_col, refresh_col = st.columns([6, 1])
    title_col.title("Vol-Adjusted Sizing Tool")
    # st.cache_data não expira sozinho -- se a Bloomberg atualizar a
    # planilha (=BDH recalcula sozinho com o Excel aberto) enquanto o
    # servidor Streamlit continua rodando, esse botão é o jeito de puxar
    # os preços novos sem precisar reiniciar `streamlit run`.
    refresh_col.button("🔄 Recarregar preços", on_click=_load_price_histories.clear, width="stretch")

    price_histories = _load_price_histories()
    if not price_histories:
        st.error(
            f"Não encontrei {CONFIG_PATH} ou não consegui ler a aba de preços configurada nele. "
            "Confira config/portfolio_risk.yaml (mesmo arquivo usado por scripts/run_var.py)."
        )
        return

    tickers = sorted(price_histories.keys())

    with st.container(border=True):
        cols = st.columns([2, 1.4, 1, 1, 1, 1, 1])
        ticker = cols[0].selectbox("Ticker BBG", tickers)
        kind_label = cols[1].radio("Instrumento", ["Preço/nível (%, Notional)", "Taxa/yield (bps, DV01)"], label_visibility="visible")
        kind = "pct" if kind_label.startswith("Preço") else "bps"
        vol_window_label = cols[2].selectbox("Janela de vol", list(VOL_WINDOW_OPTIONS.keys()), index=3)
        stop_multiple = cols[3].number_input("Stop (σ)", min_value=0.1, value=1.5, step=0.1)
        reward_risk = cols[4].number_input("R/R", min_value=0.1, value=2.0, step=0.1)
        max_loss = cols[5].number_input("Max Loss (USD)", min_value=0.0, value=50_000.0, step=1_000.0)
        side_label = cols[6].radio("Lado", ["Long", "Short"])
        side = side_label.lower()

    prices = price_histories[ticker]
    default_price = float(prices.iloc[-1])
    trade_price = st.number_input("Preço de entrada", value=default_price, format="%.6f")

    changes = change_series(prices, kind)
    n_days = VOL_WINDOW_OPTIONS[vol_window_label]
    changes_window = changes.tail(n_days) if n_days else changes
    if changes_window.empty:
        st.warning(f"{ticker} não tem histórico suficiente nessa janela.")
        return

    stats = vol_stats(changes_window)
    result = size_position(trade_price, stats.daily_vol, stop_multiple, reward_risk, max_loss, side, kind)
    unit_label = "%" if kind == "pct" else "bps"
    size_label = "Notional" if kind == "pct" else "DV01"

    st.divider()
    top = st.columns([2, 1, 1, 1, 1, 1])
    top[0].metric(f"Tamanho ajustado por vol ({size_label})", f"{result.size:,.0f}")
    top[1].metric("1σ diário", f"{stats.daily_vol:.2f}{unit_label}")
    top[2].metric(f"Stop ({stop_multiple:g}σ)", f"{result.stop_move:.2f}{unit_label}")
    top[3].metric("Preço de stop", f"{result.stop_price:.4f}")
    top[4].metric("Preço-alvo", f"{result.target_price:.4f}")
    top[5].metric("Vol anualizada", f"{stats.annualized_vol:.2f}{unit_label}")

    stat_cols = st.columns(5)
    stat_cols[0].metric("Obs.", f"{stats.n_obs}")
    stat_cols[1].metric("Média", f"{stats.mean:.3f}{unit_label}")
    stat_cols[2].metric("Mediana", f"{stats.median:.3f}{unit_label}")
    stat_cols[3].metric("Assimetria", f"{stats.skew:.2f}")
    stat_cols[4].metric("Curtose (excesso)", f"{stats.excess_kurtosis:.2f}")

    st.divider()
    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(_price_chart(prices, trade_price, result.stop_price, result.target_price), width="stretch")
    chart_cols[1].plotly_chart(_return_distribution_chart(changes_window, unit_label), width="stretch")

    st.divider()
    table_cols = st.columns([1, 1.4])
    window_df = vol_stats_by_window(changes, ROLLING_TABLE_WINDOWS)
    window_df = window_df.rename(columns={
        "janela": "Janela", "vol_anualizada": "Vol Anual. (%)", "vol_diaria": "Vol Diária (%)",
        "variacao_media": "Var. Média (%)", "variacao_acumulada": "Var. Acum. (%)",
        "max_1d": "Máx 1D (%)", "min_1d": "Mín 1D (%)",
    })
    table_cols[0].dataframe(window_df.set_index("Janela").round(3), width="stretch")
    table_cols[1].plotly_chart(_rolling_vol_chart(changes, ROLLING_CHART_WINDOWS, 252), width="stretch")


if __name__ == "__main__":
    main()
