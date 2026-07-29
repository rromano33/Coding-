"""Compara vários cenários alternativos lado a lado, pro mesmo país — mesma
ideia da planilha de simulação manual (colunas "0s / 25-25 / 25-50 / ..."),
mas usando a curva de verdade (convenção de day-count/juros certa por país)
em vez de uma aproximação linear, e reaproveitando o motor que já existe em
emrates/scenarios/.

Não precisa de Bloomberg — só da curva salva (Data/processed/curve_<país>_
<data>.json, gerada por run_daily_pricing.py) e das datas de reunião da
Input_BCs.xlsx.

Uso:
    python scripts/run_scenario_comparison.py scenarios/mexico/0s.yaml scenarios/mexico/25_25.yaml scenarios/mexico/25_50.yaml ...

Todos os YAMLs passados precisam ser do mesmo país (mesmo campo `country`).
Veja scripts/run_scenario.py pro formato de um YAML de cenário — a única
diferença aqui é que cada arquivo vira uma coluna na tabela comparativa em
vez de um relatório sozinho.
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
from emrates.scenarios.comparison import hikes_cuts_by_year_table, meeting_comparison_table, vertex_comparison_table
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.model import load_scenario


def _latest_curve_path(processed_dir: Path, country: str) -> Path | None:
    candidates = sorted(processed_dir.glob(f"curve_{country}_*.json"))
    return candidates[-1] if candidates else None


def _load_policy_rate(processed_dir: Path, country: str, as_of) -> float:
    path = processed_dir / f"policy_{country}_{as_of}.json"
    return json.loads(path.read_text())["policy_rate"] if path.exists() else 0.0


def _fmt_bps(v: float) -> str:
    return f"{v:+.1f}"


def _heat_cell(value: float, domain: float) -> str:
    color_light = diverging_color(value, domain, RED_LIGHT, GRAY_LIGHT, BLUE_LIGHT)
    color_dark = diverging_color(value, domain, RED_DARK, GRAY_DARK, BLUE_DARK)
    return f'<td class="heat-cell" style="--cell-light:{color_light};--cell-dark:{color_dark}">{_fmt_bps(value)}</td>'


def render_html(country: str, scenario_names: list[str], meeting_df, year_df, vertex_df, valuation_date) -> str:
    meeting_domain = max(5.0, *(abs(v) for name in scenario_names for v in meeting_df[name]), 5.0)
    vertex_cols = [f"{name}_delta_bps" for name in scenario_names]
    vertex_domain = max(5.0, *(abs(v) for c in vertex_cols for v in vertex_df[c]), 5.0)

    header_cols = "".join(f"<th class='num'>{name}</th>" for name in scenario_names)

    meeting_rows = []
    for _, row in meeting_df.iterrows():
        cells = "".join(_heat_cell(row[name], meeting_domain) for name in scenario_names)
        meeting_rows.append(f"<tr><td class='ink-secondary'>{row['meeting_date']}</td><td class='num'>{_fmt_bps(row['mkt'])}</td>{cells}</tr>")

    year_rows = []
    for _, row in year_df.iterrows():
        cells = "".join(_heat_cell(row[name], meeting_domain) for name in scenario_names)
        year_rows.append(f"<tr><td class='ink-secondary'>{int(row['year'])}</td><td class='num'>{_fmt_bps(row['mkt'])}</td>{cells}</tr>")

    vertex_rows = []
    for _, row in vertex_df.iterrows():
        cells = "".join(_heat_cell(row[f"{name}_delta_bps"], vertex_domain) for name in scenario_names)
        vertex_rows.append(f"<tr><td class='ink-secondary'>{row['maturity']}</td><td class='num'>{row['mkt_pct']:.3f}%</td>{cells}</tr>")

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Comparação de cenários — {country}</title>
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
  .subtitle {{ color: var(--ink-secondary); font-size: 13px; margin: 0 0 24px; }}
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
  <h1>Comparação de cenários — {country}</h1>
  <p class="subtitle">Curva de {valuation_date} · {len(scenario_names)} cenário(s): {", ".join(scenario_names)}</p>

  <div class="legend"><span>Corte a mais</span><span class="legend-bar"></span><span>Alta a mais</span></div>

  <h2>Impacto por vértice (contratos usados na curva)</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Vencimento</th><th class="num">Mkt</th>{header_cols}</tr></thead>
      <tbody>{''.join(vertex_rows)}</tbody>
    </table>
  </div>

  <h2>Δ bps por reunião, cada cenário vs. mercado</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Reunião</th><th class="num">Mkt</th>{header_cols}</tr></thead>
      <tbody>{''.join(meeting_rows)}</tbody>
    </table>
  </div>

  <h2>Total de altas/cortes por ano</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Ano</th><th class="num">Mkt</th>{header_cols}</tr></thead>
      <tbody>{''.join(year_rows)}</tbody>
    </table>
  </div>

  <footer>
    "Mkt" = já precificado pela curva, sem choque nenhum. Cada coluna de cenário soma o choque desse cenário ao que o
    mercado já precifica naquela reunião (persiste até o próximo choque do mesmo cenário).
    Δ bps por vértice = taxa do cenário menos taxa base, no vencimento de cada contrato da curva.
    Gerado por scripts/run_scenario_comparison.py.
  </footer>
</body>
</html>"""


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python scripts/run_scenario_comparison.py <cenario1.yaml> <cenario2.yaml> ...")
        sys.exit(1)
    scenario_paths = [Path(p) for p in sys.argv[1:]]

    settings = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))
    scenarios = [load_scenario(p) for p in scenario_paths]

    countries = {s.country for s in scenarios}
    if len(countries) > 1:
        print(f"Todos os cenários precisam ser do mesmo país -- recebi: {sorted(countries)}")
        sys.exit(1)
    country = scenarios[0].country
    processed_dir = Path(settings["paths"]["processed_dir"])

    curve_path = _latest_curve_path(processed_dir, country)
    if curve_path is None:
        print(f"[{country}] nenhuma curva salva em {processed_dir} -- rode run_daily_pricing.py primeiro.")
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
    current_policy_rate = _load_policy_rate(processed_dir, country, curve.valuation_date)

    scenario_curves = {s.name: build_scenario_curve(curve, meetings, s) for s in scenarios}
    scenario_names = list(scenario_curves.keys())

    meeting_df = meeting_comparison_table(curve, scenario_curves, meetings, current_policy_rate)
    year_df = hikes_cuts_by_year_table(meeting_df)
    vertex_df = vertex_comparison_table(curve, scenario_curves)

    slug = "_".join(p.stem for p in scenario_paths)
    meeting_out = processed_dir / f"scenario_comparison_meetings_{country}_{curve.valuation_date}.csv"
    year_out = processed_dir / f"scenario_comparison_years_{country}_{curve.valuation_date}.csv"
    vertex_out = processed_dir / f"scenario_comparison_vertex_{country}_{curve.valuation_date}.csv"
    html_out = processed_dir / f"scenario_comparison_{country}.html"
    meeting_df.to_csv(meeting_out, index=False)
    year_df.to_csv(year_out, index=False)
    vertex_df.to_csv(vertex_out, index=False)
    html_out.write_text(
        render_html(country, scenario_names, meeting_df, year_df, vertex_df, curve.valuation_date), encoding="utf-8"
    )

    print(f"Comparação de cenários ({country}): {', '.join(scenario_names)}\n")
    print(meeting_df.to_string(index=False))
    print("\nTotal de altas/cortes por ano:\n")
    print(year_df.to_string(index=False))
    print("\nImpacto por vértice (contratos da curva):\n")
    print(vertex_df.to_string(index=False))
    print(f"\nSalvo em {meeting_out}, {year_out}, {vertex_out} e {html_out}")


if __name__ == "__main__":
    main()
