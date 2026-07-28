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


def _json_for_script(data) -> str:
    """json.dumps() só escapa pra sintaxe JSON válida, não pra embutir com
    segurança dentro de uma tag <script> -- um valor com o texto literal
    '</script>' fecharia a tag e injetaria HTML/JS arbitrário. Escapar
    <, > e & pra \\uXXXX (mesma técnica do Django json_script) neutraliza
    isso sem mudar o valor decodificado no JS."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


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

    points_json = _json_for_script([{"date": d, "value": v} for d, v in zip(dates, values)])
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


def _fmt_position_value_compact(position: PortfolioPosition) -> str:
    suffix = "/bp" if position.position_type == "dv01" else ""
    return _fmt_usd_compact(position.position_value) + suffix


_SORTABLE_TABLE_SCRIPT = '''
<script>
if (!window.__initSortableTable) {
  window.__initSortableTable = function(tableId) {
    const table = document.getElementById(tableId);
    const thead = table.querySelector('thead');
    const bodies = Array.prototype.slice.call(table.querySelectorAll('tbody'));
    let currentCol = null;
    let currentDir = 1;
    thead.querySelectorAll('th').forEach(function(th, colIdx) {
      const type = th.getAttribute('data-sort');
      if (!type) return;
      th.addEventListener('click', function() {
        const dir = (currentCol === colIdx) ? -currentDir : -1;
        currentCol = colIdx;
        currentDir = dir;
        bodies.forEach(function(tbody) {
          // as linhas de cabeçalho de grupo (subtotal por classe) ficam
          // fixas -- só as linhas de posição dentro de cada grupo se
          // reordenam, então a agrupação nunca se perde ao ordenar.
          const rows = Array.prototype.slice.call(tbody.querySelectorAll('tr:not(.group-header-row)'));
          rows.sort(function(a, b) {
            const cellA = a.children[colIdx].getAttribute('data-sort-value');
            const cellB = b.children[colIdx].getAttribute('data-sort-value');
            const cmp = type === 'num' ? (parseFloat(cellA) - parseFloat(cellB)) : cellA.localeCompare(cellB, 'pt-BR');
            return cmp * dir;
          });
          rows.forEach(function(row) { tbody.appendChild(row); });
        });
        thead.querySelectorAll('th').forEach(function(h) { h.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
      });
    });
  };
}
</script>'''


def _build_positions_table(
    positions: list[PortfolioPosition],
    contributions_by_window: dict[str, list[float]],
    primary_window: str,
) -> str:
    """Tabela agrupada por Classe (igual ao recorte do gráfico de pizza
    "por classe"), com uma linha de subtotal por grupo e as posições
    daquele grupo logo abaixo, ordenadas pela contribuição absoluta na
    janela primária. A coluna Classe em si some da tabela -- vira o
    cabeçalho da seção, então não repete a mesma informação duas vezes e
    a tabela fica mais estreita. Colunas de contribuição por posição
    continuam clicáveis pra reordenar (dentro de cada grupo -- ver
    _SORTABLE_TABLE_SCRIPT)."""
    if not positions:
        return ""
    window_labels = list(contributions_by_window.keys())

    class_totals_by_window = {
        w: dict(_group_contributions(positions, contributions_by_window[w], lambda p: p.asset_class))
        for w in window_labels
    }
    classes_sorted = sorted(
        class_totals_by_window[primary_window], key=lambda c: -abs(class_totals_by_window[primary_window][c])
    )
    indices_by_class: dict[str, list[int]] = {}
    for i, p in enumerate(positions):
        indices_by_class.setdefault(p.asset_class, []).append(i)

    fixed_headers = [("Ativo", "text"), ("Tipo", "text"), ("Posição", "num")]
    n_fixed = len(fixed_headers)
    primary_col_idx = n_fixed + window_labels.index(primary_window)
    header_cells_parts = [f'<th data-sort="{sort_type}">{label}</th>' for label, sort_type in fixed_headers]
    for i, w in enumerate(window_labels):
        aria = ' aria-sort="descending"' if n_fixed + i == primary_col_idx else ""
        header_cells_parts.append(f'<th data-sort="num"{aria}>{html.escape(w)}</th>')
    header_cells = "".join(header_cells_parts)
    n_cols = n_fixed + len(window_labels)

    bodies = []
    for class_name in classes_sorted:
        idxs = sorted(indices_by_class[class_name], key=lambda i: -abs(contributions_by_window[primary_window][i]))
        subtotal_text = " · ".join(
            f"{html.escape(w)}: {class_totals_by_window[w][class_name]:+.1f}%" for w in window_labels
        )
        rows = "".join(
            "<tr>"
            f'<td data-sort-value="{html.escape(positions[i].asset)}">{html.escape(positions[i].asset)}</td>'
            f'<td data-sort-value="{html.escape(positions[i].position_type)}">{html.escape(positions[i].position_type.upper())}</td>'
            f'<td class="num" data-sort-value="{positions[i].position_value}">{_fmt_position_value_compact(positions[i])}</td>'
            + "".join(
                f'<td class="num" data-sort-value="{contributions_by_window[w][i]}">{contributions_by_window[w][i]:+.1f}%</td>'
                for w in window_labels
            )
            + "</tr>"
            for i in idxs
        )
        bodies.append(
            f'<tbody><tr class="group-header-row"><td colspan="{n_cols}">'
            f'<span class="group-name">{html.escape(class_name)}</span>'
            f'<span class="group-subtotal">{subtotal_text}</span>'
            f"</td></tr>{rows}</tbody>"
        )

    return f'''
<section class="card">
  <h2>Ativos do portfólio e contribuição ao risco</h2>
  <p class="footer-note" style="margin-top: -8px; margin-bottom: 14px;">Agrupado por classe, como no gráfico de pizza. Clique numa coluna para ordenar dentro de cada grupo.</p>
  <div class="table-scroll table-scroll--tall">
    <table class="data-table data-table--compact sortable-table" id="positions-table">
      <thead><tr>{header_cells}</tr></thead>
      {"".join(bodies)}
    </table>
  </div>
  <p class="footer-note">Contribuição = participação de cada ativo (ou classe, na linha de subtotal) na variância do P&amp;L do portfólio (decomposição de Euler via covariância) — soma sempre 100% dentro de cada janela, por construção, e vale tanto para o VaR histórico quanto para o paramétrico. Valores negativos reduzem o risco do portfólio (hedge).</p>
</section>
{_SORTABLE_TABLE_SCRIPT}
<script>window.__initSortableTable("positions-table");</script>'''


def _label_ink_for(hex_color: str) -> str:
    """Escolhe texto branco ou escuro pra sobrepor uma fatia colorida,
    pela luminância real da cor (nunca branco fixo -- ver marks-and-
    anatomy.md: rótulo dentro de um preenchimento colorido é a única
    exceção à regra de 'texto nunca usa a cor da série')."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#0b0b0b" if luminance > 0.4 else "#ffffff"


_PIE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
_PIE_OTHER_COLOR = "#898781"


def _group_contributions(
    positions: list[PortfolioPosition], contributions: list[float], key_fn
) -> list[tuple[str, float]]:
    totals: dict[str, float] = {}
    for p, c in zip(positions, contributions):
        key = key_fn(p)
        totals[key] = totals.get(key, 0.0) + c
    return list(totals.items())


def _group_and_cap(entries: list[tuple[str, float]], max_slices: int = 7) -> list[tuple[str, float]]:
    """Ordena por |contribuição| desc; além de `max_slices`, dobra o resto
    em 'Outros' (soma assinada) -- mesma regra da skill de dataviz pra
    categóricas: uma 9ª série nunca vira mais uma cor, vira 'Other'."""
    ordered = sorted(entries, key=lambda e: -abs(e[1]))
    if len(ordered) <= max_slices:
        return ordered
    head = ordered[:max_slices]
    tail_sum = sum(v for _, v in ordered[max_slices:])
    return head + [("Outros", tail_sum)]


def _build_pie_chart(chart_id: str, title: str, entries: list[tuple[str, float]]) -> str:
    if not entries:
        return ""
    grouped = _group_and_cap(entries)
    total_abs = sum(abs(v) for _, v in grouped) or 1.0

    cx, cy, r = 100, 100, 88
    slice_paths = []
    start_angle = -90.0
    for i, (label, value) in enumerate(grouped):
        share = abs(value) / total_abs
        sweep = share * 360.0
        end_angle = start_angle + sweep
        color = _PIE_OTHER_COLOR if label == "Outros" else _PIE_COLORS[i % len(_PIE_COLORS)]
        is_hedge = value < 0 and label != "Outros"
        large_arc = 1 if sweep > 180 else 0
        x1 = cx + r * math.cos(math.radians(start_angle))
        y1 = cy + r * math.sin(math.radians(start_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        path_d = f"M {cx},{cy} L {x1:.2f},{y1:.2f} A {r},{r} 0 {large_arc},1 {x2:.2f},{y2:.2f} Z"
        dash = ' stroke-dasharray="4 3"' if is_hedge else ""
        slice_paths.append(f'<path d="{path_d}" fill="{color}" class="pie-slice" data-idx="{i}"{dash} />')
        if share >= 0.08:
            mid_angle = math.radians((start_angle + end_angle) / 2)
            lx = cx + (r * 0.62) * math.cos(mid_angle)
            ly = cy + (r * 0.62) * math.sin(mid_angle)
            ink = _label_ink_for(color)
            slice_paths.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" class="pie-slice-label" fill="{ink}">{share * 100:.0f}%</text>'
            )
        start_angle = end_angle

    legend_rows = "".join(
        (
            f'<div class="pie-legend-row" data-idx="{i}">'
            f'<span class="pie-legend-swatch" style="background:{_PIE_OTHER_COLOR if label == "Outros" else _PIE_COLORS[i % len(_PIE_COLORS)]}"></span>'
            f'<span class="pie-legend-label">{html.escape(label)}{" (hedge)" if value < 0 and label != "Outros" else ""}</span>'
            f'<span class="pie-legend-value">{value:+.1f}%</span>'
            "</div>"
        )
        for i, (label, value) in enumerate(grouped)
    )

    data_json = _json_for_script([{"label": label, "value": value} for label, value in grouped])

    return f'''
<div class="pie-card">
  <h3>{html.escape(title)}</h3>
  <div class="pie-wrap">
    <svg viewBox="0 0 200 200" class="pie-chart" id="{chart_id}" role="img" aria-label="{html.escape(title)}">
      {"".join(slice_paths)}
    </svg>
    <div class="pie-legend">{legend_rows}</div>
  </div>
  <div class="tooltip" id="{chart_id}-tooltip" style="opacity:0"></div>
</div>
<script>
if (!window.__initPieChart) {{
  window.__initPieChart = function(chartId, data) {{
    const svg = document.getElementById(chartId);
    const card = svg.closest('.pie-card');
    const tooltip = document.getElementById(chartId + '-tooltip');
    function show(idx, evt) {{
      const d = data[idx];
      tooltip.textContent = '';
      const valueEl = document.createElement('div');
      valueEl.className = 'tooltip-value';
      valueEl.textContent = (d.value >= 0 ? '+' : '') + d.value.toFixed(1) + '%';
      const labelEl = document.createElement('div');
      labelEl.className = 'tooltip-date';
      labelEl.textContent = d.label;
      tooltip.appendChild(valueEl);
      tooltip.appendChild(labelEl);
      const rect = card.getBoundingClientRect();
      tooltip.style.opacity = 1;
      tooltip.style.left = (evt.clientX - rect.left) + 'px';
      tooltip.style.top = (evt.clientY - rect.top) + 'px';
    }}
    function hide() {{ tooltip.style.opacity = 0; }}
    card.querySelectorAll('.pie-slice').forEach(function(el) {{
      const idx = parseInt(el.getAttribute('data-idx'), 10);
      el.addEventListener('pointermove', function(evt) {{ show(idx, evt); }});
      el.addEventListener('pointerleave', hide);
    }});
    card.querySelectorAll('.pie-legend-row').forEach(function(el) {{
      const idx = parseInt(el.getAttribute('data-idx'), 10);
      el.addEventListener('pointerenter', function(evt) {{ show(idx, evt); }});
      el.addEventListener('pointerleave', hide);
    }});
  }};
}}
window.__initPieChart("{chart_id}", {data_json});
</script>'''


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
  .report { max-width: 1200px; margin: 0 auto; }
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
  .table-scroll--tall { max-height: 520px; }
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; font-size: 11px; color: var(--text-muted); font-weight: 500;
    padding: 6px 10px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface-1);
    white-space: nowrap;
  }
  .data-table td { padding: 6px 10px; border-bottom: 1px solid var(--gridline); color: var(--text-secondary); white-space: nowrap; }
  .data-table td:first-child, .data-table th:first-child { color: var(--text-primary); }
  .data-table td.num, .data-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .sortable-table th[data-sort] { cursor: pointer; user-select: none; }
  .sortable-table th[data-sort]:hover { color: var(--text-primary); }
  .sortable-table th[aria-sort="descending"]::after { content: " \\25BE"; }
  .sortable-table th[aria-sort="ascending"]::after { content: " \\25B4"; }
  .data-table--compact { font-size: 12px; }
  .data-table--compact th, .data-table--compact td { padding: 5px 8px; }
  .group-header-row td {
    padding: 8px 8px 6px; border-bottom: 1px solid var(--border);
    background: var(--page-plane); white-space: nowrap;
  }
  .group-name { font-weight: 600; color: var(--text-primary); font-size: 12px; }
  .group-subtotal { color: var(--text-secondary); font-size: 11px; margin-left: 10px; font-variant-numeric: tabular-nums; }
  .footer-note { font-size: 11px; color: var(--text-muted); margin-top: 8px; }
  .pie-row { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
  .pie-card {
    background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
    padding: 20px 22px; flex: 1 1 400px; position: relative;
  }
  .pie-card h3 { font-size: 14px; font-weight: 600; margin: 0 0 16px; color: var(--text-primary); }
  .pie-wrap { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
  .pie-chart { width: 170px; height: 170px; flex-shrink: 0; }
  .pie-slice { stroke: var(--surface-1); stroke-width: 2; cursor: pointer; transition: opacity 0.1s ease; }
  .pie-slice:hover { opacity: 0.85; }
  .pie-slice-label { font-size: 11px; font-weight: 600; pointer-events: none; }
  .pie-legend { display: flex; flex-direction: column; gap: 7px; font-size: 12px; flex: 1 1 160px; min-width: 160px; }
  .pie-legend-row { display: flex; align-items: center; gap: 7px; cursor: pointer; padding: 2px 0; }
  .pie-legend-swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
  .pie-legend-label { color: var(--text-secondary); flex: 1; }
  .pie-legend-value { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text-primary); }
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

    primary_contributions = contributions_by_window.get(primary_window, [])
    by_class = _group_contributions(positions, primary_contributions, lambda p: p.asset_class)
    by_asset = _group_contributions(positions, primary_contributions, lambda p: p.asset)
    pie_class = _build_pie_chart("pie-class", f"Contribuição por classe · {primary_window}", by_class)
    pie_asset = _build_pie_chart("pie-asset", f"Contribuição por ativo · {primary_window}", by_asset)
    pie_row = f'<div class="pie-row">{pie_class}{pie_asset}</div>' if (pie_class or pie_asset) else ""

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
    {pie_row}
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
