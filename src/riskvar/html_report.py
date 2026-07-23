"""Gera o relatório HTML autocontido de risco de portfólio: uma tabela
inicial com os ativos do portfólio (posição + contribuição ao risco),
tiles com os números principais, a tabela completa (mesma fonte que o
CSV) e um gráfico de P&L acumulado dos últimos 12 meses.

Segue as convenções da skill de dataviz do projeto: paleta padrão (uma
linha, azul), specs de marca (linha 2px, wash de área a ~10%, grid
hairline, dot de 4px+anel), crosshair+tooltip em JS puro (sem CDN — o
arquivo abre offline, sem internet) e uma vista em tabela como par de
acessibilidade do gráfico. A tabela de ativos usa texto vindo da planilha
do usuário (nome do ativo, classe) -- sempre escapado via html.escape()
antes de entrar no markup.
"""
from __future__ import annotations

import html
import json
import math
from datetime import date

import pandas as pd

from riskvar.loader import PortfolioPosition


def _fmt_usd_compact(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000_000:
        return f"{sign}${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}${v / 1_000:.1f}K"
    return f"{sign}${v:,.0f}"


def _fmt_usd_full(value: float) -> str:
    return f"{'-' if value < 0 else ''}${abs(value):,.0f}"


def _nice_step(span: float, target_ticks: int = 4) -> float:
    if span <= 0:
        return 1.0
    raw_step = span / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw_step))
    for m in (1, 2, 5, 10):
        step = m * magnitude
        if step >= raw_step:
            return step
    return raw_step * 10


def _build_performance_chart(performance_series: pd.Series) -> str:
    """Gráfico de P&L acumulado (série única, azul) com crosshair+tooltip
    em JS puro e uma vista em tabela alternativa (par de acessibilidade)."""
    values = [float(v) for v in performance_series.values]
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in performance_series.index]

    width, height = 880, 300
    pad_left, pad_right, pad_top, pad_bottom = 60, 16, 16, 30
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    y_min = min(0.0, min(values))
    y_max = max(0.0, max(values))
    if y_min == y_max:
        y_min, y_max = y_min - 1.0, y_max + 1.0
    y_pad = (y_max - y_min) * 0.08
    y_min -= y_pad
    y_max += y_pad

    def x_at(i: int) -> float:
        if len(values) == 1:
            return pad_left + plot_w / 2
        return pad_left + (i / (len(values) - 1)) * plot_w

    def y_at(v: float) -> float:
        return pad_top + (1 - (v - y_min) / (y_max - y_min)) * plot_h

    line_points = [(x_at(i), y_at(v)) for i, v in enumerate(values)]
    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in line_points)
    y_zero = y_at(0.0)
    area_d = line_d + f" L {line_points[-1][0]:.1f},{y_zero:.1f} L {line_points[0][0]:.1f},{y_zero:.1f} Z"

    step = _nice_step(y_max - y_min, target_ticks=4)
    y_ticks = []
    t = math.ceil(y_min / step) * step
    while t <= y_max:
        y_ticks.append(t)
        t += step

    gridlines = "".join(
        f'<line x1="{pad_left}" x2="{width - pad_right}" y1="{y_at(t):.1f}" y2="{y_at(t):.1f}" class="grid" />'
        for t in y_ticks
    )
    y_labels = "".join(
        f'<text x="{pad_left - 10}" y="{y_at(t) + 4:.1f}" class="axis-label" text-anchor="end">{_fmt_usd_compact(t)}</text>'
        for t in y_ticks
    )

    n_x_ticks = min(6, len(dates))
    if len(dates) > 1:
        x_idx = sorted({round(i * (len(dates) - 1) / (n_x_ticks - 1)) for i in range(n_x_ticks)})
    else:
        x_idx = [0]
    x_labels = "".join(
        f'<text x="{x_at(i):.1f}" y="{height - pad_bottom + 20}" class="axis-label" text-anchor="middle">'
        f'{pd.Timestamp(performance_series.index[i]).strftime("%b/%y")}</text>'
        for i in x_idx
    )

    end_x, end_y = line_points[-1]
    end_value = values[-1]
    end_class = "good" if end_value >= 0 else "critical"

    svg = f'''<svg viewBox="0 0 {width} {height}" class="perf-chart" role="img" preserveAspectRatio="xMidYMid meet"
     aria-label="P&amp;L acumulado do portfólio nos últimos 12 meses, terminando em {_fmt_usd_full(end_value)}">
  <line x1="{pad_left}" x2="{width - pad_right}" y1="{y_zero:.1f}" y2="{y_zero:.1f}" class="baseline" />
  {gridlines}
  <path d="{area_d}" class="area-fill" />
  <path d="{line_d}" class="line-mark" fill="none" />
  <circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" class="end-dot {end_class}" />
  <text x="{end_x - 8:.1f}" y="{end_y - 10:.1f}" text-anchor="end" class="end-label {end_class}">{_fmt_usd_compact(end_value)}</text>
  {y_labels}
  {x_labels}
  <line id="perf-crosshair" x1="0" x2="0" y1="{pad_top}" y2="{height - pad_bottom}" class="crosshair" style="opacity:0" />
  <circle id="perf-crosshair-dot" r="4" class="crosshair-dot" style="opacity:0" />
  <rect id="perf-hit-area" x="{pad_left}" y="{pad_top}" width="{plot_w}" height="{plot_h}" fill="transparent" />
</svg>'''

    points_json = json.dumps([{"date": d, "value": v} for d, v in zip(dates, values)])
    table_rows = "".join(
        f'<tr><td>{pd.Timestamp(d).strftime("%d/%m/%Y")}</td><td class="num">{_fmt_usd_full(v)}</td></tr>'
        for d, v in zip(dates, values)
    )

    return f'''
<section class="card">
  <div class="card-head">
    <h2>Performance do portfólio — P&amp;L acumulado, últimos 12 meses</h2>
    <button type="button" id="perf-table-toggle" class="ghost-btn" aria-expanded="false">Ver dados em tabela</button>
  </div>
  <div class="chart-wrap">
    {svg}
    <div id="perf-tooltip" class="tooltip" style="opacity:0"></div>
  </div>
  <div id="perf-table-wrap" class="table-scroll" hidden>
    <table class="data-table">
      <thead><tr><th>Data</th><th>P&amp;L acumulado</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
</section>
<script>
(function() {{
  const points = {points_json};
  const svg = document.querySelector('.perf-chart');
  const hitArea = document.getElementById('perf-hit-area');
  const crosshair = document.getElementById('perf-crosshair');
  const dot = document.getElementById('perf-crosshair-dot');
  const tooltip = document.getElementById('perf-tooltip');
  const plotLeft = {pad_left};
  const plotWidth = {plot_w};
  const plotTop = {pad_top};
  const plotHeight = {plot_h};
  const yMin = {y_min};
  const yMax = {y_max};

  function yFor(v) {{
    return plotTop + (1 - (v - yMin) / (yMax - yMin)) * plotHeight;
  }}

  function fmtCompact(v) {{
    const sign = v < 0 ? '-' : '';
    const a = Math.abs(v);
    if (a >= 1e9) return sign + '$' + (a / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return sign + '$' + (a / 1e6).toFixed(1) + 'M';
    if (a >= 1e3) return sign + '$' + (a / 1e3).toFixed(1) + 'K';
    return sign + '$' + a.toFixed(0);
  }}

  function fmtDate(iso) {{
    const [y, m, d] = iso.split('-');
    return d + '/' + m + '/' + y;
  }}

  function pointerMove(evt) {{
    const rect = svg.getBoundingClientRect();
    const scaleX = {width} / rect.width;
    const px = (evt.clientX - rect.left) * scaleX;
    let idx = Math.round(((px - plotLeft) / plotWidth) * (points.length - 1));
    idx = Math.max(0, Math.min(points.length - 1, idx));
    const p = points[idx];
    const x = plotLeft + (points.length > 1 ? (idx / (points.length - 1)) * plotWidth : plotWidth / 2);
    const y = yFor(p.value);

    crosshair.setAttribute('x1', x);
    crosshair.setAttribute('x2', x);
    crosshair.style.opacity = 1;
    dot.setAttribute('cx', x);
    dot.setAttribute('cy', y);
    dot.style.opacity = 1;

    tooltip.textContent = '';
    const valueEl = document.createElement('div');
    valueEl.className = 'tooltip-value';
    valueEl.textContent = fmtCompact(p.value);
    const dateEl = document.createElement('div');
    dateEl.className = 'tooltip-date';
    dateEl.textContent = fmtDate(p.date);
    tooltip.appendChild(valueEl);
    tooltip.appendChild(dateEl);

    const scaleFactor = rect.width / {width};
    tooltip.style.opacity = 1;
    tooltip.style.left = (x * scaleFactor) + 'px';
    tooltip.style.top = (y * scaleFactor) + 'px';
  }}

  function pointerLeave() {{
    crosshair.style.opacity = 0;
    dot.style.opacity = 0;
    tooltip.style.opacity = 0;
  }}

  hitArea.addEventListener('pointermove', pointerMove);
  hitArea.addEventListener('pointerleave', pointerLeave);

  const toggle = document.getElementById('perf-table-toggle');
  const tableWrap = document.getElementById('perf-table-wrap');
  toggle.addEventListener('click', function() {{
    const isHidden = tableWrap.hasAttribute('hidden');
    if (isHidden) {{
      tableWrap.removeAttribute('hidden');
      toggle.setAttribute('aria-expanded', 'true');
      toggle.textContent = 'Ocultar tabela';
    }} else {{
      tableWrap.setAttribute('hidden', '');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.textContent = 'Ver dados em tabela';
    }}
  }});
}})();
</script>'''


def _fmt_position_value(position: PortfolioPosition) -> str:
    suffix = "/bp" if position.position_type == "dv01" else ""
    return _fmt_usd_full(position.position_value) + suffix


def _build_positions_table(
    positions: list[PortfolioPosition],
    contributions_by_window: dict[str, list[float]],
    primary_window: str,
) -> str:
    if not positions:
        return ""
    window_labels = list(contributions_by_window.keys())
    order = sorted(range(len(positions)), key=lambda i: -abs(contributions_by_window[primary_window][i]))

    header_cells = "<th>Ativo</th><th>Classe</th><th>Tipo</th><th>Posição</th>" + "".join(
        f"<th>Contrib. {html.escape(w)}</th>" for w in window_labels
    )
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(positions[i].asset)}</td>"
        f"<td>{html.escape(positions[i].asset_class)}</td>"
        f"<td>{html.escape(positions[i].position_type.upper())}</td>"
        f"<td class=\"num\">{_fmt_position_value(positions[i])}</td>"
        + "".join(f'<td class="num">{contributions_by_window[w][i]:+.1f}%</td>' for w in window_labels)
        + "</tr>"
        for i in order
    )
    return f'''
<section class="card">
  <h2>Ativos do portfólio e contribuição ao risco</h2>
  <div class="table-scroll">
    <table class="data-table">
      <thead><tr>{header_cells}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <p class="footer-note">Contribuição = participação de cada ativo na variância do P&amp;L do portfólio (decomposição de Euler via covariância) — soma sempre 100% dentro de cada janela, por construção, e vale tanto para o VaR histórico quanto para o paramétrico. Valores negativos reduzem o risco do portfólio (hedge).</p>
</section>'''


def _stat_tile(label: str, value: str) -> str:
    return f'<div class="stat-tile"><div class="stat-label">{label}</div><div class="stat-value">{value}</div></div>'


def _build_stat_tiles(report_df: pd.DataFrame, primary_confidence_label: str) -> str:
    tiles = []
    for window in report_df["janela"].unique():
        row = report_df[(report_df["janela"] == window) & (report_df["confianca"] == primary_confidence_label)]
        if row.empty:
            continue
        r = row.iloc[0]
        tiles.append(_stat_tile(f"VaR histórico · {window} · {primary_confidence_label}", _fmt_usd_compact(r["var_historico"])))
        tiles.append(_stat_tile(f"VaR paramétrico · {window} · {primary_confidence_label}", _fmt_usd_compact(r["var_parametrico"])))
        tiles.append(_stat_tile(f"Vol diária · {window}", _fmt_usd_compact(r["vol_diaria"])))
        tiles.append(_stat_tile(f"Vol anualizada · {window}", _fmt_usd_compact(r["vol_anualizada"])))
    return "".join(tiles)


def _build_report_table(report_df: pd.DataFrame) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{r['janela']}</td>"
        f"<td>{r['confianca']}</td>"
        f"<td class=\"num\">{int(r['n_obs'])}</td>"
        f"<td class=\"num\">{_fmt_usd_full(r['var_historico'])}</td>"
        f"<td class=\"num\">{_fmt_usd_full(r['var_parametrico'])}</td>"
        f"<td class=\"num\">{_fmt_usd_full(r['vol_diaria'])}</td>"
        f"<td class=\"num\">{_fmt_usd_full(r['vol_anualizada'])}</td>"
        "</tr>"
        for _, r in report_df.iterrows()
    )
    return f'''
<section class="card">
  <h2>VaR e vol por janela de estimação</h2>
  <div class="table-scroll">
    <table class="data-table">
      <thead><tr><th>Janela</th><th>Confiança</th><th>N obs.</th><th>VaR histórico</th><th>VaR paramétrico</th><th>Vol diária</th><th>Vol anualizada</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>'''


_CSS = '''
<style>
  .viz-root {
    color-scheme: light;
    --page-plane:     #f9f9f7;
    --surface-1:      #fcfcfb;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --gridline:       #e1e0d9;
    --baseline:       #c3c2b7;
    --series-1:       #2a78d6;
    --delta-good:     #006300;
    --delta-critical: #d03b3b;
    --border:         rgba(11,11,11,0.10);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page-plane);
    color: var(--text-primary);
    padding: 40px 24px;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      color-scheme: dark;
      --page-plane:     #0d0d0d;
      --surface-1:      #1a1a19;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --gridline:       #2c2c2a;
      --baseline:       #383835;
      --series-1:       #3987e5;
      --delta-good:     #0ca30c;
      --delta-critical: #e66767;
      --border:         rgba(255,255,255,0.10);
    }
  }
  :root[data-theme="dark"] .viz-root {
    color-scheme: dark;
    --page-plane:     #0d0d0d;
    --surface-1:      #1a1a19;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --series-1:       #3987e5;
    --delta-good:     #0ca30c;
    --delta-critical: #e66767;
    --border:         rgba(255,255,255,0.10);
  }
  .viz-root * { box-sizing: border-box; }
  .report { max-width: 920px; margin: 0 auto; }
  .report-header { margin-bottom: 28px; }
  .report-header h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.01em; }
  .report-header p { font-size: 13px; color: var(--text-secondary); margin: 0; }
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--border);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 24px;
  }
  .stat-tile { background: var(--surface-1); padding: 16px 18px; }
  .stat-label { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; line-height: 1.3; }
  .stat-value { font-size: 20px; font-weight: 600; font-variant-numeric: proportional-nums; }
  .card {
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 22px 22px;
    margin-bottom: 20px;
  }
  .card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .card h2 { font-size: 14px; font-weight: 600; margin: 0 0 14px; color: var(--text-primary); }
  .ghost-btn {
    font: inherit; font-size: 12px; color: var(--text-secondary);
    background: transparent; border: 1px solid var(--border); border-radius: 6px;
    padding: 5px 10px; cursor: pointer; margin-bottom: 14px;
  }
  .ghost-btn:hover { color: var(--text-primary); border-color: var(--text-muted); }
  .chart-wrap { position: relative; }
  .perf-chart { width: 100%; height: auto; display: block; overflow: visible; }
  .grid { stroke: var(--gridline); stroke-width: 1; }
  .baseline { stroke: var(--baseline); stroke-width: 1; }
  .line-mark { stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
  .area-fill { fill: var(--series-1); opacity: 0.10; stroke: none; }
  .end-dot { fill: var(--series-1); stroke: var(--surface-1); stroke-width: 2; }
  .end-dot.good { fill: var(--delta-good); }
  .end-dot.critical { fill: var(--delta-critical); }
  .end-label { font-size: 12px; font-weight: 600; }
  .end-label.good { fill: var(--delta-good); }
  .end-label.critical { fill: var(--delta-critical); }
  .axis-label { font-size: 10px; fill: var(--text-muted); }
  .crosshair { stroke: var(--text-muted); stroke-width: 1; }
  .crosshair-dot { fill: var(--series-1); stroke: var(--surface-1); stroke-width: 2; }
  #perf-hit-area { cursor: crosshair; }
  .tooltip {
    position: absolute; transform: translate(-50%, -130%);
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 10px; pointer-events: none; white-space: nowrap;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12); transition: opacity 0.08s ease;
  }
  .tooltip-value { font-size: 13px; font-weight: 600; color: var(--text-primary); }
  .tooltip-date { font-size: 11px; color: var(--text-muted); }
  .table-scroll { overflow-x: auto; max-height: 340px; overflow-y: auto; }
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; font-size: 11px; color: var(--text-muted); font-weight: 500;
    padding: 6px 10px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface-1);
  }
  .data-table td { padding: 6px 10px; border-bottom: 1px solid var(--gridline); color: var(--text-secondary); }
  .data-table td:first-child, .data-table th:first-child { color: var(--text-primary); }
  .data-table td.num, .data-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .footer-note { font-size: 11px; color: var(--text-muted); margin-top: 8px; }
</style>
'''


def render_report_html(
    report_df: pd.DataFrame,
    performance_series: pd.Series,
    valuation_date: date,
    n_positions: int,
    positions: list[PortfolioPosition],
    contributions_by_window: dict[str, list[float]],
    primary_window: str,
    base_currency: str = "USD",
) -> str:
    """Retorna o conteúdo (CSS + corpo) do relatório -- sem <!doctype>/<html>/
    <head>/<body>, para ser embrulhado tanto por save_standalone_html quanto
    pelo publicador de Artifacts.

    `contributions_by_window`: window_label -> lista de % de contribuição
    ao risco, mesma ordem/tamanho que `positions` (ver
    riskvar.pnl_series.risk_contribution_pct). `primary_window` decide por
    qual janela a tabela de ativos é ordenada (maior contribuição
    absoluta primeiro)."""
    primary_confidence_label = report_df["confianca"].iloc[0]
    positions_table = _build_positions_table(positions, contributions_by_window, primary_window)
    stat_tiles = _build_stat_tiles(report_df, primary_confidence_label)
    performance_chart = _build_performance_chart(performance_series)
    report_table = _build_report_table(report_df)

    return f'''{_CSS}
<div class="viz-root">
  <div class="report">
    <div class="report-header">
      <h1>Risco de portfólio</h1>
      <p>{n_positions} posições · base {base_currency} · dados de {valuation_date.strftime("%d/%m/%Y")}</p>
    </div>
    {positions_table}
    <div class="stat-grid">{stat_tiles}</div>
    {performance_chart}
    {report_table}
    <p class="footer-note">VaR de 1 dia, histórico e paramétrico (variância-covariância). "Janela" é o período de P&amp;L histórico usado para estimar cada métrica, não o horizonte do VaR.</p>
  </div>
</div>
'''


def save_standalone_html(content: str, out_path, title: str = "Risco de portfólio") -> None:
    doc = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body>
{content}
</body>
</html>
'''
    out_path.write_text(doc, encoding="utf-8")
