"""Gera o HTML interativo pra distribuir pra mesa: lê o MESMO histórico de
preços/taxas da aba "Preços" que scripts/run_var.py usa (config/
portfolio_risk.yaml), mas NÃO embute nenhuma posição sua -- só o histórico
de mercado. Quem abrir o arquivo preenche as próprias posições e os
números de risco recalculam ali mesmo, em JavaScript, sem precisar de
Python nem de sessão Bloomberg.

O arquivo gerado é uma FOTO do mercado no momento em que este script rodou
-- o HTML deixa isso explícito num banner no topo. Pra atualizar os
preços, rode este script de novo (com a planilha atualizada) e redistribua
o arquivo.

python scripts/build_interactive_var.py
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riskvar.interactive_report import render_interactive_html, save_standalone_html
from riskvar.price_history import load_price_history

CONFIG_PATH = Path("config/portfolio_risk.yaml")


def main() -> None:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"\n{CONFIG_PATH} não existe -- este script usa o mesmo config pessoal do "
            "scripts/run_var.py (só a parte de histórico de preços, nenhuma posição sua vai "
            "pro arquivo gerado). Veja config/portfolio_risk.example.yaml pra criar o seu."
        )
    settings = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    price_history_cfg = settings["price_history"]
    price_histories = load_price_history(
        settings["paths"]["portfolio_xlsx"],
        price_history_cfg["sheet"],
        price_history_cfg.get("ticker_row_label", "BBG"),
    )
    print(f"{len(price_histories)} tickers com histórico carregados de {settings['paths']['portfolio_xlsx']}")

    valuation_date = max(series.index.max() for series in price_histories.values()).date()
    generated_at = datetime.now()

    html_content = render_interactive_html(
        price_histories,
        settings["lookback_windows"],
        settings["confidence_levels"],
        settings["trading_days_per_year"],
        settings.get("base_currency", "USD"),
        valuation_date,
        generated_at,
        stress_factors=settings.get("stress_factors"),
        stress_scenarios=settings.get("stress_scenarios"),
    )

    output_dir = Path(settings["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"var_interativo_{date.today()}.html"
    save_standalone_html(html_content, out_path, title="Risco de portfólio — interativo")
    print(f"Dados de mercado até {valuation_date:%d/%m/%Y}")
    print(f"HTML interativo salvo em {out_path} -- pode compartilhar com a mesa (não tem posição nenhuma sua nele).")


if __name__ == "__main__":
    main()
