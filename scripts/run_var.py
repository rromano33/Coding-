"""Lê a planilha do portfólio (posições + histórico de preços, já
preenchido no Excel via Bloomberg) e calcula VaR (histórico e
paramétrico) e vol do portfólio, usando janelas de 3M e 12M de dados
históricos. VaR em si é sempre de 1 dia -- ver config/portfolio_risk.yaml
e riskvar/var_metrics.py.

Não depende de sessão Bloomberg em Python (BBComm/xbbg) -- o histórico
vem pronto da aba "Preços" da própria planilha, puxado no Excel via
=BDH(...). Ver riskvar/price_history.py.

python scripts/run_var.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riskvar.html_report import render_report_html, save_standalone_html
from riskvar.loader import PortfolioLoader
from riskvar.pnl_series import filter_positions_with_history, portfolio_pnl_series, risk_contribution_pct
from riskvar.price_history import load_price_history
from riskvar.report import build_risk_report


CONFIG_PATH = Path("config/portfolio_risk.yaml")
EXAMPLE_CONFIG_PATH = Path("config/portfolio_risk.example.yaml")


def main() -> None:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"\n{CONFIG_PATH} não existe ainda -- esse arquivo é pessoal (não vem no git), cada "
            "trader tem o seu, apontando pra própria planilha de portfólio.\n\n"
            f"Primeira vez rodando isso? Copie o template e edite o caminho da sua planilha:\n"
            f"  cp {EXAMPLE_CONFIG_PATH} {CONFIG_PATH}\n"
            f"  (depois edite paths.portfolio_xlsx em {CONFIG_PATH} pro caminho da sua planilha)\n"
        )
    settings = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    loader = PortfolioLoader(settings["paths"]["portfolio_xlsx"], settings["sheet"], settings["columns"])
    positions = loader.load()
    print(f"{len(positions)} posições carregadas de {settings['paths']['portfolio_xlsx']}")

    price_history_cfg = settings["price_history"]
    price_histories_full = load_price_history(
        settings["paths"]["portfolio_xlsx"],
        price_history_cfg["sheet"],
        price_history_cfg.get("ticker_row_label", "BBG"),
    )

    positions, missing_tickers = filter_positions_with_history(positions, price_histories_full.keys())
    if missing_tickers:
        print(
            f"Sem histórico na aba {price_history_cfg['sheet']!r} para: {', '.join(missing_tickers)} "
            "-- excluí essas posições do cálculo de VaR/vol (confira se o ticker bate entre as duas abas)."
        )
    if not positions:
        raise SystemExit("Nenhuma posição com histórico válido -- nada para calcular.")

    end = date.today()
    pnl_by_window = {}
    contributions_by_window = {}
    for window_label, n_days in settings["lookback_windows"].items():
        price_histories = {p.ticker: price_histories_full[p.ticker].tail(n_days + 1) for p in positions}
        pnl_by_window[window_label] = portfolio_pnl_series(positions, price_histories).tail(n_days)
        contributions_by_window[window_label] = risk_contribution_pct(positions, price_histories)

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
        positions=positions,
        contributions_by_window=contributions_by_window,
        primary_window=performance_window,
        base_currency=settings.get("base_currency", "USD"),
    )
    html_path = output_dir / f"var_report_{end}.html"
    save_standalone_html(html_content, html_path)
    print(f"Relatório HTML salvo em {html_path}")


if __name__ == "__main__":
    main()
