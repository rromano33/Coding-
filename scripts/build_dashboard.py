"""Gera um dashboard HTML estático (autocontido, sem internet) com a
precificação de cada Banco Central nas próximas 8 reuniões, e quanto isso
mudou numa janela de 1 e 5 dias.

Precisa de scripts/run_daily_pricing.py já ter rodado pelo menos uma vez
(as colunas Δ1d/Δ5d só aparecem quando houver dias suficientes de
histórico acumulado em Data/processed/).

python scripts/build_dashboard.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emrates.reports.colors import BLUE_DARK, BLUE_LIGHT, GRAY_DARK, GRAY_LIGHT, RED_DARK, RED_LIGHT, diverging_color

# Order matters for layout: LatAm fills row 1 (4 cols), CEMEA fills row 2,
# with south_africa placed last so it lands in the same column as colombia
# (directly below it) in the fixed 4-column card grid — see .grid CSS below.
COUNTRIES = ["brazil", "mexico", "chile", "colombia", "poland", "czech", "hungary", "south_africa"]
COUNTRY_LABELS = {
    "brazil": "Brasil",
    "mexico": "México",
    "chile": "Chile",
    "colombia": "Colômbia",
    "south_africa": "África do Sul",
    "poland": "Polônia",
    "czech": "Rep. Tcheca",
    "hungary": "Hungria",
}
MEETINGS_SHOWN = 8


def find_snapshots(processed_dir: Path, country: str) -> dict[date, Path]:
    pattern = re.compile(rf"priced_bc_{re.escape(country)}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$")
    out = {}
    for p in processed_dir.glob(f"priced_bc_{country}_*.csv"):
        m = pattern.match(p.name)
        if m:
            out[date.fromisoformat(m.group(1))] = p
    return out


def nearest_at_or_before(snapshots: dict[date, Path], cutoff: date) -> Path | None:
    candidates = [d for d in snapshots if d <= cutoff]
    return snapshots[max(candidates)] if candidates else None


def load_policy_rate(processed_dir: Path, country: str, as_of: date) -> float | None:
    p = processed_dir / f"policy_{country}_{as_of}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())["policy_rate"]


def cumulative_lookup(path: Path | None) -> dict:
    if path is None:
        return {}
    df = pd.read_csv(path, parse_dates=["meeting_date"])
    return dict(zip(df["meeting_date"].dt.date, df["cumulative_change_from_spot_bps"]))


def build_country_data(processed_dir: Path, country: str) -> dict | None:
    snapshots = find_snapshots(processed_dir, country)
    if not snapshots:
        return None
    latest_date = max(snapshots)
    latest_df = pd.read_csv(snapshots[latest_date], parse_dates=["meeting_date"]).head(MEETINGS_SHOWN)

    one_day_path = nearest_at_or_before(snapshots, latest_date - timedelta(days=1))
    five_day_path = nearest_at_or_before(snapshots, latest_date - timedelta(days=5))
    one_day_map = cumulative_lookup(one_day_path)
    five_day_map = cumulative_lookup(five_day_path)

    rows = []
    for _, r in latest_df.iterrows():
        meeting_date = r["meeting_date"].date()
        cumulative = r["cumulative_change_from_spot_bps"]
        rows.append(
            {
                "meeting_date": meeting_date,
                "implied_change_bps": r["implied_change_bps"],
                "cumulative_bps": cumulative,
                "delta_1d": (cumulative - one_day_map[meeting_date]) if meeting_date in one_day_map else None,
                "delta_5d": (cumulative - five_day_map[meeting_date]) if meeting_date in five_day_map else None,
            }
        )

    return {
        "country": country,
        "label": COUNTRY_LABELS[country],
        "as_of": latest_date,
        "policy_rate": load_policy_rate(processed_dir, country, latest_date),
        "rows": rows,
        "has_1d": one_day_path is not None,
        "has_5d": five_day_path is not None,
    }


def fmt_bps(v) -> str:
    if v is None or v != v:
        return "—"
    return f"{v:+.0f}"


def render_country_card(c: dict, domain: float) -> str:
    policy_txt = f'{c["policy_rate"] * 100:.3f}%' if c["policy_rate"] is not None else "—"
    rows_html = []
    for row in c["rows"]:
        bps = row["cumulative_bps"]
        bar_t = max(-1.0, min(1.0, bps / domain)) if domain else 0.0
        bar_pct = abs(bar_t) * 50
        # left:50% anchors the bar's left edge at center and grows rightward (hikes);
        # right:50% anchors the right edge at center and grows leftward (cuts).
        bar_side = "left" if bar_t >= 0 else "right"
        bar_color = "var(--diverge-blue)" if bar_t >= 0 else "var(--diverge-red)"
        rows_html.append(
            f"""
            <tr>
              <td class="ink-secondary">{row['meeting_date']}</td>
              <td class="num">{fmt_bps(row['implied_change_bps'])}</td>
              <td class="num cumulative-cell">
                <div class="mini-bar-track">
                  <div class="mini-bar" style="background:{bar_color};width:{bar_pct:.1f}%;{bar_side}:50%"></div>
                </div>
                <span class="mini-bar-value">{fmt_bps(bps)}</span>
              </td>
              <td class="num {'ink-muted' if row['delta_1d'] is None else ''}">{fmt_bps(row['delta_1d'])}</td>
              <td class="num {'ink-muted' if row['delta_5d'] is None else ''}">{fmt_bps(row['delta_5d'])}</td>
            </tr>"""
        )
    return f"""
    <section class="card">
      <header class="card-header">
        <h3>{c['label']}</h3>
        <span class="policy-rate">taxa atual: <strong>{policy_txt}</strong></span>
      </header>
      <table class="country-table">
        <thead>
          <tr>
            <th>Reunião</th><th class="num">Δ bps</th><th class="num">Acumulado</th>
            <th class="num">Δ 1d</th><th class="num">Δ 5d</th>
          </tr>
        </thead>
        <tbody>{"".join(rows_html)}</tbody>
      </table>
    </section>"""


def main() -> None:
    settings = yaml.safe_load(open("config/settings.yaml", encoding="utf-8"))
    processed_dir = Path(settings["paths"]["processed_dir"])

    countries_data = []
    for country in COUNTRIES:
        data = build_country_data(processed_dir, country)
        if data is None:
            print(f"[{country}] sem priced_bc salvo ainda — pulei no dashboard.")
            continue
        countries_data.append(data)

    if not countries_data:
        print("Nenhum país com dado salvo — rode run_daily_pricing.py primeiro.")
        return

    # Two separate domains: the heatmap shows the per-meeting change (small,
    # typically single digits to ~20bps), the cards' mini-bar/Acumulado
    # column shows the cumulative change (grows across the 8 meetings) — one
    # shared domain would wash out the heatmap's colors.
    max_abs_meeting = max(
        (abs(row["implied_change_bps"]) for c in countries_data for row in c["rows"] if row["implied_change_bps"] == row["implied_change_bps"]),
        default=1.0,
    )
    domain_meeting = max(15.0, max_abs_meeting)
    max_abs_cumulative = max(
        (abs(row["cumulative_bps"]) for c in countries_data for row in c["rows"] if row["cumulative_bps"] == row["cumulative_bps"]),
        default=1.0,
    )
    domain_cumulative = max(30.0, max_abs_cumulative)

    # Countries as columns, meetings (ordinal — 1ª, 2ª, ...) as rows. Ordinal
    # labels rather than calendar months: each country's meetings fall on
    # different dates, so a shared row only makes sense by meeting order, and
    # "M1" read as "Mês 1" (month) was ambiguous in Portuguese anyway. Cells
    # show the change priced AT that meeting (not the cumulative) — the
    # cumulative path is in the per-country cards below.
    heat_header = "".join(f'<th class="heat-col">{c["label"]}</th>' for c in countries_data)
    heat_rows = []
    for i in range(MEETINGS_SHOWN):
        cells = []
        for c in countries_data:
            if i < len(c["rows"]):
                row = c["rows"][i]
                bps = row["implied_change_bps"]
                color_light = diverging_color(bps, domain_meeting, RED_LIGHT, GRAY_LIGHT, BLUE_LIGHT)
                color_dark = diverging_color(bps, domain_meeting, RED_DARK, GRAY_DARK, BLUE_DARK)
                title = f'{c["label"]} · {row["meeting_date"]} · {fmt_bps(bps)} bps nesta reunião'
                cells.append(
                    f'<td class="heat-cell" style="--cell-light:{color_light};--cell-dark:{color_dark}" '
                    f'title="{title}">{fmt_bps(bps)}</td>'
                )
            else:
                cells.append('<td class="heat-cell heat-empty">—</td>')
        heat_rows.append(f'<tr><th class="heat-row-label">{i + 1}ª reunião</th>{"".join(cells)}</tr>')

    any_1d = any(c["has_1d"] for c in countries_data)
    any_5d = any(c["has_5d"] for c in countries_data)
    history_note = ""
    if not any_1d and not any_5d:
        history_note = (
            '<p class="history-note">Ainda não há histórico suficiente para Δ 1d/5d — '
            "essas colunas aparecem conforme você for rodando run_daily_pricing.py em dias seguintes.</p>"
        )
    elif not any_5d:
        history_note = '<p class="history-note">Δ 5d ainda não disponível — precisa de 5 dias de histórico acumulado.</p>'

    generated_at = countries_data[0]["as_of"]
    cards_html = "".join(render_country_card(c, domain_cumulative) for c in countries_data)

    html = f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Precificação de Bancos Centrais — LatAm &amp; CEMEA</title>
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
  h3 {{ font-size: 15px; margin: 0; }}
  .subtitle {{ color: var(--ink-secondary); font-size: 13px; margin: 0 0 24px; }}
  .ink-secondary {{ color: var(--ink-secondary); }}
  .ink-muted {{ color: var(--ink-muted); }}
  .legend {{ display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ink-secondary); margin-bottom: 12px; }}
  .legend-bar {{ width: 140px; height: 10px; border-radius: 5px;
    background: linear-gradient(90deg, var(--diverge-red), var(--diverge-mid), var(--diverge-blue)); }}
  .heat-scroll {{ overflow-x: auto; background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px; margin-bottom: 32px; }}
  table.heatmap {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  table.heatmap th, table.heatmap td {{ padding: 8px 10px; text-align: center; white-space: nowrap; }}
  .heat-row-label {{ text-align: left !important; color: var(--ink-primary); font-weight: 600; }}
  .heat-col {{ color: var(--ink-muted); font-weight: 500; font-size: 11px; }}
  .heat-cell {{ background: var(--cell-light); border-radius: 6px; font-variant-numeric: tabular-nums;
    color: var(--ink-primary); }}
  @media (prefers-color-scheme: dark) {{ .heat-cell {{ background: var(--cell-dark); }} }}
  .heat-empty {{ color: var(--ink-muted); background: transparent !important; }}
  .history-note {{ font-size: 12px; color: var(--ink-muted); margin: -20px 0 24px; }}
  /* Fixed 4 columns (not auto-fill) so layout order is predictable: row 1 is
     LatAm, row 2 is CEMEA, and south_africa (last in COUNTRIES) lands in
     colombia's column, directly below it. */
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
  @media (max-width: 1100px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  @media (max-width: 560px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }}
  .policy-rate {{ font-size: 12px; color: var(--ink-secondary); }}
  table.country-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  table.country-table th {{ text-align: left; color: var(--ink-muted); font-weight: 500; font-size: 11px;
    padding: 4px 6px; border-bottom: 1px solid var(--gridline); }}
  table.country-table td {{ padding: 6px; border-bottom: 1px solid var(--gridline); font-variant-numeric: tabular-nums; }}
  .num {{ text-align: right; }}
  .cumulative-cell {{ position: relative; min-width: 90px; }}
  .mini-bar-track {{ position: relative; height: 10px; background: var(--gridline); border-radius: 5px;
    margin-bottom: 2px; overflow: hidden; }}
  .mini-bar {{ position: absolute; top: 0; height: 100%; border-radius: 4px; }}
  .mini-bar-value {{ font-size: 11px; color: var(--ink-secondary); }}
  footer {{ margin-top: 32px; font-size: 11px; color: var(--ink-muted); }}
</style>
</head>
<body>
  <h1>Precificação de Bancos Centrais — LatAm &amp; CEMEA</h1>
  <p class="subtitle">Próximas {MEETINGS_SHOWN} reuniões por país, gerado a partir da curva de {generated_at}</p>

  <div class="legend">
    <span>Corte precificado</span>
    <span class="legend-bar"></span>
    <span>Alta precificada</span>
  </div>

  <div class="heat-scroll">
    <table class="heatmap">
      <thead><tr><th></th>{heat_header}</tr></thead>
      <tbody>{''.join(heat_rows)}</tbody>
    </table>
  </div>
  {history_note}

  <div class="grid">
    {cards_html}
  </div>

  <footer>
    Mapa de calor: bps precificados NAQUELA reunião (implied_change_bps) — não é acumulado.
    Acumulado (nas tabelas por país) = soma dos bps precificados desde hoje até aquela reunião (cumulative_change_from_spot_bps).
    Δ 1d/5d = variação do acumulado frente à curva salva 1/5 dias corridos atrás (usa o dia útil mais recente disponível).
    Gerado por scripts/build_dashboard.py.
  </footer>
</body>
</html>"""

    out_path = processed_dir / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard gerado -> {out_path}")


if __name__ == "__main__":
    main()
