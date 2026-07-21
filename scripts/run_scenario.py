"""Roda um cenário alternativo (choques em reuniões específicas do BC) sobre
a curva já salva por run_daily_pricing.py e mostra o impacto: (1) no caminho
de reuniões precificado, (2) em cada vértice de mercado (contrato DI1) usado
pra montar a curva — pra ajudar a decidir se vale a pena se posicionar em
algum contrato.

Não precisa de Bloomberg — só da curva salva (Data/processed/curve_<país>_
<data>.json) e das datas de reunião da Input_BCs.xlsx. Assim dá pra testar
vários cenários rapidamente, editando só o YAML.

Uso:
    python scripts/run_scenario.py scenarios/brazil/example_hawkish.yaml

Formato do cenário (veja scenarios/brazil/ pra mais exemplos):
    name: "Copom mais hawkish nas próximas 2 reuniões"
    country: brazil
    shocks:
      - meeting_date: 2026-08-06
        shock_bps: -25   # negativo = corta mais do que o mercado precifica
      - meeting_date: 2026-09-17
        shock_bps: -15   # soma ao choque anterior (persiste) -> -40bps dali pra frente
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.central_banks.meeting_dates import upcoming_meetings
from emrates.data.calendars import CalendarSet
from emrates.data.curve_store import load_curve
from emrates.data.excel_loader import InputsBCsLoader
from emrates.reports.colors import BLUE_DARK, BLUE_LIGHT, GRAY_DARK, GRAY_LIGHT, RED_DARK, RED_LIGHT, diverging_color
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.model import load_scenario
from emrates.scenarios.report import scenario_meeting_report, vertex_impact_report


def _latest_curve_path(processed_dir: Path, country: str) -> Path | None:
    candidates = sorted(processed_dir.glob(f"curve_{country}_*.json"))
    return candidates[-1] if candidates else None


def _load_policy_rate(processed_dir: Path, country: str, as_of) -> float:
    path = processed_dir / f"policy_{country}_{as_of}.json"
    return json.loads(path.read_text())["policy_rate"] if path.exists() else 0.0


def _fmt_bps(v: float) -> str:
    return f"{v:+.1f}"


def render_html(scenario, meeting_df, vertex_df, valuation_date) -> str:
    max_abs_vertex = max((abs(v) for v in vertex_df["delta_bps"]), default=1.0)
    vertex_domain = max(5.0, max_abs_vertex)
    max_abs_meeting = max((abs(v) for v in meeting_df["delta_vs_base_bps"]), default=1.0)
    meeting_domain = max(5.0, max_abs_meeting)

    vertex_rows = []
    for _, row in vertex_df.iterrows():
        bps = row["delta_bps"]
        color_light = diverging_color(bps, vertex_domain, RED_LIGHT, GRAY_LIGHT, BLUE_LIGHT)
        color_dark = diverging_color(bps, vertex_domain, RED_DARK, GRAY_DARK, BLUE_DARK)
        vertex_rows.append(
            f"""
            <tr>
              <td class="ink-secondary">{row['maturity']}</td>
              <td class="num">{row['base_rate_pct']:.3f}%</td>
              <td class="num">{row['scenario_rate_pct']:.3f}%</td>
              <td class="heat-cell" style="--cell-light:{color_light};--cell-dark:{color_dark}">{_fmt_bps(bps)}</td>
            </tr>"""
        )

    meeting_rows = []
    for _, row in meeting_df.iterrows():
        bps = row["delta_vs_base_bps"]
        color_light = diverging_color(bps, meeting_domain, RED_LIGHT, GRAY_LIGHT, BLUE_LIGHT)
        color_dark = diverging_color(bps, meeting_domain, RED_DARK, GRAY_DARK, BLUE_DARK)
        meeting_rows.append(
            f"""
            <tr>
              <td class="ink-secondary">{row['meeting_date']}</td>
              <td class="num">{_fmt_bps(row['base_implied_change_bps'])}</td>
              <td class="num">{_fmt_bps(row['scenario_implied_change_bps'])}</td>
              <td class="num">{_fmt_bps(row['base_cumulative_bps'])}</td>
              <td class="num">{_fmt_bps(row['scenario_cumulative_bps'])}</td>
              <td class="heat-cell" style="--cell-light:{color_light};--cell-dark:{color_dark}">{_fmt_bps(bps)}</td>
            </tr>"""
        )

    shocks_txt = ", ".join(f"{s.meeting_date}: {s.shock_bps:+.0f}bps" for s in scenario.shocks)

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Cenário — {scenario.name}</title>
<style>
  :root {{
    color-scheme: light;
    --surface-1: #fcfcfb; --page: #f9f9f7;
    --ink-primary: #0b0b0b; --ink-secondary: #52514e; --ink-muted: #898781;
    --gridline: #e1e0d9; --border: rgba(11,11,11,0.10);
    --diverge-blue: #2a78d6; --diverge-red: #e34948; --diverge-mid: #f0efec;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface-1: #1a1a19; --page: #0d0d0d;
      --ink-primary: #ffffff; --ink-secondary: #c3c2b7; --ink-muted: #898781;
      --gridline: #2c2c2a; --border: rgba(255,255,255,0.10);
      --diverge-blue: #3987e5; --diverge-red: #e66767; --diverge-mid: #383835;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px; background: var(--page); color: var(--ink-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 32px 0 10px; }}
  .subtitle {{ color: var(--ink-secondary); font-size: 13px; margin: 0 0 4px; }}
  .shocks {{ color: var(--ink-secondary); font-size: 13px; margin: 0 0 24px; }}
  .ink-secondary {{ color: var(--ink-secondary); }}
  .legend {{ display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ink-secondary); margin-bottom: 4px; }}
  .legend-bar {{ width: 140px; height: 10px; border-radius: 5px;
    background: linear-gradient(90deg, var(--diverge-red), var(--diverge-mid), var(--diverge-blue)); }}
  .panel {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ padding: 8px 10px; text-align: left; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  th {{ color: var(--ink-muted); font-weight: 500; font-size: 11px; border-bottom: 1px solid var(--gridline); }}
  td {{ border-bottom: 1px solid var(--gridline); }}
  .num {{ text-align: right; }}
  .heat-cell {{ background: var(--cell-light); border-radius: 6px; text-align: right; font-weight: 600; }}
  @media (prefers-color-scheme: dark) {{ .heat-cell {{ background: var(--cell-dark); }} }}
  footer {{ margin-top: 32px; font-size: 11px; color: var(--ink-muted); }}
</style>
</head>
<body>
  <h1>Cenário: {scenario.name}</h1>
  <p class="subtitle">{scenario.country} · curva de {valuation_date}</p>
  <p class="shocks">Choques aplicados — {shocks_txt}</p>

  <div class="legend"><span>Corte a mais</span><span class="legend-bar"></span><span>Alta a mais</span></div>

  <h2>Impacto por vértice (contratos usados na curva)</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Vencimento</th><th class="num">Base</th><th class="num">Cenário</th><th class="num">Δ bps</th></tr></thead>
      <tbody>{''.join(vertex_rows)}</tbody>
    </table>
  </div>

  <h2>Caminho de reuniões: base vs. cenário</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Reunião</th><th class="num">Δ base</th><th class="num">Δ cenário</th>
        <th class="num">Acum. base</th><th class="num">Acum. cenário</th><th class="num">Δ vs. base</th></tr></thead>
      <tbody>{''.join(meeting_rows)}</tbody>
    </table>
  </div>

  <footer>
    Δ bps por vértice = taxa do cenário menos taxa base, no vencimento de cada contrato da curva.
    Além da última reunião modelada, o cenário mantém o formato da curva de mercado, deslocado pelo choque ainda em vigor.
    Gerado por scripts/run_scenario.py.
  </footer>
</body>
</html>"""


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python scripts/run_scenario.py <caminho para o yaml do cenário>")
        sys.exit(1)
    scenario_path = Path(sys.argv[1])

    settings = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))
    scenario = load_scenario(scenario_path)
    country = scenario.country
    processed_dir = Path(settings["paths"]["processed_dir"])

    curve_path = _latest_curve_path(processed_dir, country)
    if curve_path is None:
        print(f"[{country}] nenhuma curva salva em {processed_dir} — rode run_daily_pricing.py primeiro.")
        sys.exit(1)

    column_map = {
        "dates": settings["dates_columns"],
        "dates_sheet": settings["sheets"]["dates_sheet"],
        "tickers": settings["tickers_columns"],
        "tickers_sheet": settings["sheets"]["tickers_sheet"],
        "positions": settings["positions_columns"],
        "positions_sheet": settings["sheets"]["positions_sheet"],
    }
    loader = InputsBCsLoader(settings["paths"]["inputs_bcs"], column_map)
    meetings_by_country = loader.load_meeting_dates()
    calendars = CalendarSet.from_holiday_frame(loader.load_holidays())

    curve = load_curve(curve_path, calendars.get(country))
    horizon = settings["reporting"]["meetings_horizon"]
    meetings = upcoming_meetings(meetings_by_country.get(country, []), curve.valuation_date, horizon + 1)

    scenario_curve = build_scenario_curve(curve, meetings, scenario)
    current_policy_rate = _load_policy_rate(processed_dir, country, curve.valuation_date)

    meeting_df = scenario_meeting_report(curve, scenario_curve, meetings, current_policy_rate)
    vertex_df = vertex_impact_report(curve, scenario_curve)

    slug = scenario_path.stem
    meeting_out = processed_dir / f"scenario_{country}_{slug}_{curve.valuation_date}.csv"
    vertex_out = processed_dir / f"scenario_vertex_{country}_{slug}_{curve.valuation_date}.csv"
    html_out = processed_dir / f"scenario_{country}_{slug}.html"
    meeting_df.to_csv(meeting_out, index=False)
    vertex_df.to_csv(vertex_out, index=False)
    html_out.write_text(render_html(scenario, meeting_df, vertex_df, curve.valuation_date), encoding="utf-8")

    print(f"Cenário '{scenario.name}' ({country}):\n")
    print(meeting_df.to_string(index=False))
    print("\nImpacto por vértice (contratos da curva):\n")
    print(vertex_df.to_string(index=False))
    print(f"\nSalvo em {meeting_out}, {vertex_out} e {html_out}")


if __name__ == "__main__":
    main()
