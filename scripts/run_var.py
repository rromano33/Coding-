"""Roda localmente (Bloomberg Terminal ativo): lê a planilha do portfólio,
busca histórico de PX_LAST na Bloomberg para cada ticker e calcula VaR
(histórico e paramétrico) e vol do portfólio, usando janelas de 3M e 12M
de dados históricos. VaR em si é sempre de 1 dia -- ver
config/portfolio_risk.yaml e riskvar/var_metrics.py.

python scripts/run_var.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.data.bbg_client import BbgClient
from riskvar.html_report import render_report_html, save_standalone_html
from riskvar.loader import PortfolioLoader
from riskvar.pnl_series import filter_positions_with_history, portfolio_pnl_series
from riskvar.report import build_risk_report


def main() -> None:
    settings = yaml.safe_load(open("config/portfolio_risk.yaml", encoding="utf-8"))

    loader = PortfolioLoader(settings["paths"]["portfolio_xlsx"], settings["sheet"], settings["columns"])
    positions = loader.load()
    print(f"{len(positions)} posições carregadas de {settings['paths']['portfolio_xlsx']}")

    bbg = BbgClient(settings["paths"]["bbg_cache_dir"])
    end = date.today()
    start = end - timedelta(days=settings["history_buffer_calendar_days"])

    tickers = sorted({p.ticker for p in positions})
    history_df = bbg.history(tickers, start, end)

    positions, missing_tickers = filter_positions_with_history(positions, history_df.columns)
    if missing_tickers:
        print(
            f"Sem histórico na Bloomberg para: {', '.join(missing_tickers)} "
            "-- excluí essas posições do cálculo de VaR/vol (confira o ticker na planilha)."
        )
    if not positions:
        raise SystemExit("Nenhuma posição com histórico válido na Bloomberg -- nada para calcular.")
    tickers = sorted({p.ticker for p in positions})

    pnl_by_window = {}
    for window_label, n_days in settings["lookback_windows"].items():
        price_histories = {t: history_df[t].tail(n_days + 1) for t in tickers}
        pnl_by_window[window_label] = portfolio_pnl_series(positions, price_histories).tail(n_days)

    report = build_risk_report(
        pnl_by_window, settings["confidence_levels"], settings["trading_days_per_year"]
    )
    print()
    print(report.to_string(index=False))

    output_dir = Path(settings["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"var_report_{end}.csv"
    report.to_csv(out_path, index=False)
    print(f"\nSalvo em {out_path}")

    # janela de performance = a mais longa configurada (tipicamente "12M") --
    # o gráfico do HTML mostra o P&L acumulado ao longo dela.
    performance_window = max(settings["lookback_windows"], key=settings["lookback_windows"].get)
    performance_series = pnl_by_window[performance_window].cumsum()

    html_content = render_report_html(
        report,
        performance_series,
        valuation_date=end,
        n_positions=len(positions),
        base_currency=settings.get("base_currency", "USD"),
    )
    html_path = output_dir / f"var_report_{end}.html"
    save_standalone_html(html_content, html_path)
    print(f"Relatório HTML salvo em {html_path}")


if __name__ == "__main__":
    main()
