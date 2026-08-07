"""Verifica que a matemática em JavaScript de riskvar/interactive_report.py
(a VERSÃO EM JS de var_metrics.py/pnl_series.py/stress.py) bate com a
implementação Python original -- gera um dataset sintético determinístico,
calcula os números dos dois lados (Python direto; JS rodando de verdade
num Chromium headless via Playwright) e compara.

Rode isso depois de qualquer mudança na engine JS embutida no HTML
interativo (_JS_ENGINE em interactive_report.py) -- é fácil digitar uma
fórmula certa em Python e errada em JS (ou vice-versa) sem que nenhum
teste pytest pegue, já que o pytest não executa JavaScript.

Tolerância: exata pros cálculos históricos (VaR/ES/diversificação/piores
dias -- só ordenação e média, sem aproximação numérica nos dois lados);
~1e-3 relativo pros paramétricos e stress test (usam a inversa da normal,
que é uma aproximação racional em JS vs scipy.stats.norm em Python --
a diferença fica na 5ª-6ª casa significativa, irrelevante pra um número
em $, mas precisa de uma tolerância um pouco mais folgada que "==").

Ferramenta de desenvolvimento, não faz parte do fluxo diário -- exige
`playwright` (`pip install playwright && playwright install chromium`),
que por isso NÃO está em requirements.txt (build_interactive_var.py, o
script que gera o HTML de verdade pra distribuir, não depende disso).

python scripts/verify_interactive_var.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riskvar.interactive_report import render_interactive_html, save_standalone_html
from riskvar.loader import PortfolioPosition
from riskvar.pnl_series import diversification_benefit, portfolio_pnl_series, worst_days
from riskvar.report import build_risk_report
from riskvar.stress import factor_change_series, run_stress_scenarios

REL_TOL_EXACT = 1e-9
REL_TOL_APPROX = 1e-3


def _close(a: float, b: float, rel_tol: float) -> bool:
    return abs(a - b) <= rel_tol * max(abs(a), abs(b), 1.0)


def build_synthetic_dataset():
    rng = np.random.default_rng(7)
    n = 300
    dates = pd.bdate_range(end=date(2026, 8, 7), periods=n)
    price_histories = {
        "TESTA Index": pd.Series(100 + np.cumsum(rng.normal(0, 1.2, n)), index=dates),
        "TESTB Curncy": pd.Series(5 + np.cumsum(rng.normal(0, 0.03, n)), index=dates),
        "SPX Index": pd.Series(5000 + np.cumsum(rng.normal(0, 20, n)), index=dates),
        "USGG10YR Index": pd.Series(4.3 + np.cumsum(rng.normal(0, 0.02, n)), index=dates),
    }
    positions = [
        PortfolioPosition(asset="A", ticker="TESTA Index", position_type="notional", position_value=1_000_000),
        PortfolioPosition(asset="B", ticker="TESTB Curncy", position_type="dv01", position_value=5_000),
    ]
    return price_histories, positions


def compute_expected(price_histories, positions):
    lookback_windows = {"3M": 63, "12M": 252}
    confidence_levels = [0.95, 0.99]
    stress_factors = {"spx": {"ticker": "SPX Index", "kind": "pct_return"}, "ust10y": {"ticker": "USGG10YR Index", "kind": "bps_change"}}
    stress_scenarios = [
        {"name": "S&P -5%", "shocks": {"spx": -0.05}},
        {"name": "UST10y +20bps", "shocks": {"ust10y": 20}},
        {"name": "Risk-off combinado", "shocks": {"spx": -0.05, "ust10y": 20}},
    ]

    pnl_by_window = {}
    for window_label, n_days in lookback_windows.items():
        ph = {p.ticker: price_histories[p.ticker].tail(n_days + 1) for p in positions}
        pnl_by_window[window_label] = portfolio_pnl_series(positions, ph).tail(n_days)

    report_df = build_risk_report(pnl_by_window, confidence_levels, 252)
    ph_12m = {p.ticker: price_histories[p.ticker].tail(lookback_windows["12M"] + 1) for p in positions}
    div = diversification_benefit(positions, ph_12m, confidence_levels[0])
    worst = worst_days(pnl_by_window["12M"], n=10)
    factor_series = {name: factor_change_series(price_histories[cfg["ticker"]], cfg["kind"]) for name, cfg in stress_factors.items()}
    stress_results = run_stress_scenarios(pnl_by_window["12M"], factor_series, stress_scenarios)

    return {
        "lookback_windows": lookback_windows,
        "confidence_levels": confidence_levels,
        "stress_factors": stress_factors,
        "stress_scenarios": stress_scenarios,
        "report_df": report_df,
        "diversification": div,
        "worst_days": worst,
        "stress_results": stress_results,
    }


def run_js_side(price_histories, expected, out_html: Path) -> dict:
    html = render_interactive_html(
        price_histories, expected["lookback_windows"], expected["confidence_levels"], 252, "USD",
        date(2026, 8, 7), datetime(2026, 8, 7, 18, 30),
        stress_factors=expected["stress_factors"], stress_scenarios=expected["stress_scenarios"],
    )
    save_standalone_html(html, out_html, title="verify")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))
        page.goto(out_html.as_uri())

        rows = page.locator("#positions-tbody tr")
        rows.nth(0).locator(".pos-ticker").select_option("TESTA Index")
        rows.nth(0).locator(".pos-type").select_option("notional")
        rows.nth(0).locator(".pos-value").fill("1000000")
        page.click("#add-position-btn")
        rows = page.locator("#positions-tbody tr")
        rows.nth(1).locator(".pos-ticker").select_option("TESTB Curncy")
        rows.nth(1).locator(".pos-type").select_option("dv01")
        rows.nth(1).locator(".pos-value").fill("5000")
        page.wait_for_timeout(500)

        result = page.evaluate('''
            () => {
                const positions = readPositions();
                const windowNames = Object.keys(CONFIG.lookback_windows);
                const byWindow = {};
                const pnlPairsByWindow = {};
                windowNames.forEach(window => {
                    const nDays = CONFIG.lookback_windows[window];
                    const pairs = windowPortfolioPnl(positions, nDays);
                    pnlPairsByWindow[window] = pairs;
                    const pnlArr = pairs.map(p => p[1]);
                    const metricsByConf = {};
                    CONFIG.confidence_levels.forEach(conf => { metricsByConf[conf] = riskMetrics(pnlArr, conf, CONFIG.trading_days_per_year); });
                    byWindow[window] = metricsByConf;
                });
                const div = diversificationBenefit(positions, 252, CONFIG.confidence_levels[0]);
                const worst = worstDays(pnlPairsByWindow['12M'], 10);

                const primaryPairs = pnlPairsByWindow['12M'];
                const pnlByDate = new Map(primaryPairs);
                const factorNames = Object.keys(CONFIG.stress_factors);
                const factorArrsAligned = {};
                factorNames.forEach(name => {
                    const cfg = CONFIG.stress_factors[name];
                    const trimmed = PRICE_HISTORY[cfg.ticker].slice(-(252 + 1));
                    const changeSeries = positionPnlSeries({ type: cfg.kind === 'pct_return' ? 'notional' : 'dv01', value: 1 }, trimmed);
                    factorArrsAligned[name] = new Map(changeSeries);
                });
                const primaryDates = primaryPairs.map(p => p[0]);
                const commonDates = primaryDates.filter(d => factorNames.every(name => factorArrsAligned[name].has(d)));
                const pnlAligned = commonDates.map(d => pnlByDate.get(d));
                const factorArrsFinal = {};
                factorNames.forEach(name => { factorArrsFinal[name] = commonDates.map(d => factorArrsAligned[name].get(d)); });
                const { betas, rSquared } = fitFactorSensitivities(pnlAligned, factorArrsFinal);
                const stressResults = CONFIG.stress_scenarios.map(scenario => {
                    let impact = 0;
                    Object.keys(scenario.shocks).forEach(factor => { impact += (betas[factor] || 0) * scenario.shocks[factor]; });
                    return { name: scenario.name, pnl_impact: impact, r_squared: rSquared };
                });
                return { byWindow, diversification: div, worst, stressResults };
            }
        ''')
        browser.close()
        if console_errors:
            raise RuntimeError(f"Erros no console JS da página: {console_errors}")
        return result


def main() -> None:
    price_histories, positions = build_synthetic_dataset()
    expected = compute_expected(price_histories, positions)
    out_html = Path("/tmp/verify_interactive_var.html")
    actual = run_js_side(price_histories, expected, out_html)

    failures = []
    conf_key_map = {"95%": "0.95", "99%": "0.99"}
    for _, r in expected["report_df"].iterrows():
        js = actual["byWindow"][r["janela"]][conf_key_map[r["confianca"]]]
        checks = [
            ("var_historico", "varHistorical", REL_TOL_EXACT),
            ("var_parametrico", "varParametric", REL_TOL_APPROX),
            ("es_historico", "esHistorical", REL_TOL_EXACT),
            ("es_parametrico", "esParametric", REL_TOL_APPROX),
            ("vol_diaria", "dailyVol", REL_TOL_EXACT),
            ("vol_anualizada", "annualizedVol", REL_TOL_EXACT),
        ]
        for py_key, js_key, tol in checks:
            if not _close(r[py_key], js[js_key], tol):
                failures.append(f"{r['janela']} {r['confianca']} {py_key}: py={r[py_key]} js={js[js_key]}")

    div = expected["diversification"]
    div_js = actual["diversification"]
    for py_val, js_val, name in [
        (div.standalone_var_sum, div_js["standaloneSum"], "standalone_var_sum"),
        (div.portfolio_var, div_js["portfolioVar"], "portfolio_var"),
        (div.benefit_pct, div_js["benefitPct"], "benefit_pct"),
    ]:
        if not _close(py_val, js_val, REL_TOL_EXACT):
            failures.append(f"diversification {name}: py={py_val} js={js_val}")

    worst_py = expected["worst_days"]
    worst_js = actual["worst"]
    for i, (_, r) in enumerate(worst_py.iterrows()):
        if str(r["data"]) != worst_js[i][0] or not _close(r["pnl"], worst_js[i][1], REL_TOL_EXACT):
            failures.append(f"worst_days[{i}]: py=({r['data']}, {r['pnl']}) js={worst_js[i]}")

    for i, r in enumerate(expected["stress_results"]):
        js = actual["stressResults"][i]
        if not _close(r.pnl_impact, js["pnl_impact"], REL_TOL_APPROX) or not _close(r.r_squared, js["r_squared"], REL_TOL_APPROX):
            failures.append(f"stress[{r.name}]: py=(impact={r.pnl_impact}, r2={r.r_squared}) js={js}")

    if failures:
        print(f"FALHOU -- {len(failures)} divergência(s) entre Python e JS:")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"OK -- JS bate com Python em todos os {len(expected['report_df'])} pontos de VaR/ES/vol, "
          f"diversificação, {len(worst_py)} piores dias e {len(expected['stress_results'])} cenários de stress.")


if __name__ == "__main__":
    main()
