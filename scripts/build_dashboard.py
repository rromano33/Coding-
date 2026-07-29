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

from emrates.central_banks.meeting_dates import upcoming_meetings
from emrates.data.calendars import CalendarSet
from emrates.data.curve_store import load_curve
from emrates.data.excel_loader import InputsBCsLoader
from emrates.reports.colors import BLUE_DARK, BLUE_LIGHT, GRAY_DARK, GRAY_LIGHT, RED_DARK, RED_LIGHT, diverging_color
from emrates.scenarios.comparison import hikes_cuts_by_year_table, meeting_comparison_table, vertex_comparison_table
from emrates.scenarios.curve import build_scenario_curve
from emrates.scenarios.lab_data import build_lab_skeleton
from emrates.scenarios.model import load_scenario

SCENARIOS_DIR = Path("scenarios")

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


def _latest_curve_path(processed_dir: Path, country: str) -> Path | None:
    candidates = sorted(processed_dir.glob(f"curve_{country}_*.json"))
    return candidates[-1] if candidates else None


def _load_input_sources(settings: dict):
    """Loads Input_BCs.xlsx (meeting dates + holiday calendars) once, shared
    across every country's scenario section. Returns (meetings_by_country,
    calendars), or None if the file isn't available here — the scenario
    section is skipped in that case, base dashboard still renders."""
    column_map = {
        "dates": settings["dates_columns"],
        "dates_sheet": settings["sheets"]["dates_sheet"],
        "tickers": settings["tickers_columns"],
        "tickers_sheet": settings["sheets"]["tickers_sheet"],
        "positions": settings["positions_columns"],
        "positions_sheet": settings["sheets"]["positions_sheet"],
    }
    try:
        loader = InputsBCsLoader(settings["paths"]["inputs_bcs"], column_map)
        meetings_by_country = loader.load_meeting_dates()
        calendars = CalendarSet.from_holiday_frame(loader.load_holidays())
    except FileNotFoundError:
        return None
    return meetings_by_country, calendars


def build_scenario_section_data(settings: dict, processed_dir: Path, country: str, country_label: str) -> dict | None:
    scenario_files = sorted((SCENARIOS_DIR / country).glob("*.yaml")) if (SCENARIOS_DIR / country).is_dir() else []
    if not scenario_files:
        return None

    curve_path = _latest_curve_path(processed_dir, country)
    if curve_path is None:
        return None

    sources = _load_input_sources(settings)
    if sources is None:
        return None
    meetings_by_country, calendars = sources

    curve = load_curve(curve_path, calendars.get(country))
    horizon = settings["reporting"]["meetings_horizon"]
    meetings = upcoming_meetings(meetings_by_country.get(country, []), curve.valuation_date, horizon + 1)
    if len(meetings) < 2:
        return None

    current_policy_rate = load_policy_rate(processed_dir, country, curve.valuation_date) or 0.0

    scenario_curves = {}
    scenario_labels = {}
    for path in scenario_files:
        try:
            scenario = load_scenario(path)
            scenario_curves[path.stem] = build_scenario_curve(curve, meetings, scenario)
            scenario_labels[path.stem] = scenario.name
        except ValueError as exc:
            # e.g. an exemplo_template.yaml whose placeholder meeting_date
            # hasn't been edited yet — skip just this one file rather than
            # crashing the whole dashboard build.
            print(f"[{country}] pulei cenário {path.name}: {exc}")

    if not scenario_curves:
        return None

    meeting_df = meeting_comparison_table(curve, scenario_curves, meetings, current_policy_rate)
    year_df = hikes_cuts_by_year_table(meeting_df)
    vertex_df = vertex_comparison_table(curve, scenario_curves)

    return {
        "label": country_label,
        "scenario_labels": scenario_labels,
        "meeting_df": meeting_df,
        "year_df": year_df,
        "vertex_df": vertex_df,
    }


def render_scenario_section(data: dict) -> str:
    slugs = list(data["scenario_labels"])
    header_cells = "".join(
        f'<th class="num" title="{data["scenario_labels"][s]}">{s}</th>' for s in slugs
    )

    max_abs_meeting = max((abs(v) for s in slugs for v in data["meeting_df"][s]), default=1.0)
    domain_meeting = max(15.0, max_abs_meeting)
    meeting_rows = []
    for _, row in data["meeting_df"].iterrows():
        cells = "".join(_heat_td(row[s], domain_meeting) for s in slugs)
        meeting_rows.append(f'<tr><td class="ink-secondary">{row["meeting_date"]}</td><td class="num">{fmt_bps(row["mkt"])}</td>{cells}</tr>')

    max_abs_year = max((abs(v) for s in slugs for v in data["year_df"][s]), default=1.0)
    domain_year = max(15.0, max_abs_year)
    year_rows = []
    for _, row in data["year_df"].iterrows():
        cells = "".join(_heat_td(row[s], domain_year) for s in slugs)
        year_rows.append(f'<tr><td class="ink-secondary">{int(row["year"])}</td><td class="num">{fmt_bps(row["mkt"])}</td>{cells}</tr>')

    max_abs_vertex = max((abs(row[f"{s}_delta_bps"]) for _, row in data["vertex_df"].iterrows() for s in slugs), default=1.0)
    domain_vertex = max(5.0, max_abs_vertex)
    vertex_rows = []
    for _, row in data["vertex_df"].iterrows():
        cells = "".join(_heat_td(row[f"{s}_delta_bps"], domain_vertex) for s in slugs)
        vertex_rows.append(f'<tr><td class="ink-secondary">{row["maturity"]}</td><td class="num">{row["mkt_pct"]:.3f}%</td>{cells}</tr>')

    return f"""
    <section class="scenario-section">
      <h3>{data['label']} — cenários</h3>
      <p class="scenario-note">Colunas: mkt (precificado hoje) + cada cenário em scenarios/&lt;país&gt;/*.yaml (passe o mouse no cabeçalho pro nome completo).</p>

      <h4>Bps por reunião</h4>
      <div class="panel"><table class="compare">
        <thead><tr><th>Reunião</th><th class="num">mkt</th>{header_cells}</tr></thead>
        <tbody>{"".join(meeting_rows)}</tbody>
      </table></div>

      <h4>Hikes/cuts por ano</h4>
      <div class="panel"><table class="compare">
        <thead><tr><th>Ano</th><th class="num">mkt</th>{header_cells}</tr></thead>
        <tbody>{"".join(year_rows)}</tbody>
      </table></div>

      <h4>Impacto por vértice (Δ bps vs. mkt)</h4>
      <div class="panel"><table class="compare">
        <thead><tr><th>Vencimento</th><th class="num">mkt</th>{header_cells}</tr></thead>
        <tbody>{"".join(vertex_rows)}</tbody>
      </table></div>
    </section>"""


def _heat_td(value: float, domain: float) -> str:
    color_light = diverging_color(value, domain, RED_LIGHT, GRAY_LIGHT, BLUE_LIGHT)
    color_dark = diverging_color(value, domain, RED_DARK, GRAY_DARK, BLUE_DARK)
    return f'<td class="heat-cell" style="--cell-light:{color_light};--cell-dark:{color_dark}">{fmt_bps(value)}</td>'


def _json_for_script(data) -> str:
    """json.dumps() só escapa pra sintaxe JSON válida, não pra embutir com
    segurança dentro de uma tag <script> -- um valor com o texto literal
    '</script>' fecharia a tag e injetaria HTML/JS arbitrário. Escapar
    <, > e & pra \\uXXXX (mesma técnica do Django json_script) neutraliza
    isso. Aqui os valores são todos números/datas computados pelo próprio
    Python (não texto vindo de planilha do usuário), mas é grátis manter
    o mesmo hábito seguro do resto do projeto (ver riskvar/html_report.py)."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_lab_section_data(settings: dict, processed_dir: Path, country: str, country_label: str) -> dict | None:
    """Skeleton pra aba interativa de cenário (ver LAB_SCRIPT): o usuário
    digita um caminho ABSOLUTO de bps por reunião (não um choque relativo
    ao mercado -- Ricardo, 29/07/2026: 'a surpresa só faz sentido assim')
    e o navegador recalcula o impacto na hora, sem depender de Python
    rodando de novo. Ver emrates/scenarios/lab_data.py pro que exatamente
    é pré-computado aqui vs. o que fica por conta do JS."""
    curve_path = _latest_curve_path(processed_dir, country)
    if curve_path is None:
        return None

    sources = _load_input_sources(settings)
    if sources is None:
        return None
    meetings_by_country, calendars = sources

    curve = load_curve(curve_path, calendars.get(country))
    horizon = settings["reporting"]["meetings_horizon"]
    meetings = upcoming_meetings(meetings_by_country.get(country, []), curve.valuation_date, horizon)
    if not meetings:
        return None

    current_policy_rate = load_policy_rate(processed_dir, country, curve.valuation_date) or 0.0
    skeleton = build_lab_skeleton(curve, meetings, current_policy_rate)

    return {"country": country, "label": country_label, "skeleton": skeleton}


def render_lab_section(lab_data_list: list[dict]) -> str:
    if not lab_data_list:
        return ""

    tab_buttons = "".join(
        f'<button type="button" class="lab-tab-btn{" lab-tab-active" if i == 0 else ""}" '
        f'data-country="{d["country"]}">{d["label"]}</button>'
        for i, d in enumerate(lab_data_list)
    )

    panels = []
    for i, d in enumerate(lab_data_list):
        country = d["country"]
        skeleton = d["skeleton"]
        input_rows = "".join(
            f'<tr><td class="ink-secondary">{m["date"]}</td>'
            f'<td class="num">{m["market_forward_pct"]:.3f}%</td>'
            f'<td class="num"><input type="number" class="lab-bps-input" step="1" value="0" data-idx="{j}"></td></tr>'
            for j, m in enumerate(skeleton["meetings"])
        )
        panels.append(f"""
    <div class="lab-panel{' lab-panel-active' if i == 0 else ''}" id="lab-panel-{country}">
      <table class="lab-input-table">
        <thead><tr><th>Reunião</th><th class="num">Mercado hoje</th><th class="num">Seu cenário (Δ bps)</th></tr></thead>
        <tbody>{input_rows}</tbody>
      </table>
      <div class="lab-actions">
        <button type="button" class="lab-calc-btn" data-country="{country}">Calcular</button>
        <button type="button" class="lab-reset-btn" data-country="{country}">Limpar</button>
      </div>
      <div class="lab-results" id="lab-results-{country}" hidden>
        <h4>Δ bps por reunião</h4>
        <div class="panel"><table class="compare">
          <thead><tr><th>Reunião</th><th class="num">Mercado</th><th class="num">Seu cenário</th>
            <th class="num">Δ vs. mercado</th><th class="num">Nível (seu cenário)</th></tr></thead>
          <tbody id="lab-meeting-tbody-{country}"></tbody>
        </table></div>
        <h4>Impacto por vértice (contratos usados na curva)</h4>
        <div class="panel"><table class="compare">
          <thead><tr><th>Vencimento</th><th class="num">Mercado</th><th class="num">Seu cenário</th>
            <th class="num">Δ bps</th></tr></thead>
          <tbody id="lab-vertex-tbody-{country}"></tbody>
        </table></div>
      </div>
      <script type="application/json" id="lab-skeleton-{country}">{_json_for_script(skeleton)}</script>
    </div>""")

    return f"""
    <section class="lab-section">
      <h3>Cenários interativos</h3>
      <p class="scenario-note">Digite o corte/alta absoluto (bps) que você acha que acontece em cada reunião — não é
        um choque em cima do que o mercado já precifica, é o caminho inteiro. Clique "Calcular" pra ver o impacto
        na hora, sem precisar rodar nada de novo.</p>
      <div class="lab-tabs">{tab_buttons}</div>
      {"".join(panels)}
    </section>
    {LAB_SCRIPT}"""


LAB_SCRIPT = """
<script>
(function() {
  function discountFactor(ratePct, tau, compounding) {
    var r = ratePct / 100;
    if (compounding === 'linear') return 1 / (1 + r * tau);
    return Math.pow(1 + r, -tau); // exponential e compounded_daily -- ver conventions/compounding.py
  }

  function zeroRatePct(df, tau, compounding) {
    if (compounding === 'linear') return ((1 / df - 1) / tau) * 100;
    return (Math.pow(df, -1 / tau) - 1) * 100;
  }

  function fmtBps(v) {
    var sign = v >= 0 ? '+' : '';
    return sign + v.toFixed(1);
  }

  function fmtPct(v) {
    return v.toFixed(3) + '%';
  }

  function heatStyle(value, domain) {
    // Só as custom properties -- o background em si vem da regra
    // .heat-cell do stylesheet (light usa --cell-light, o media query de
    // dark mode troca pra --cell-dark). Fixar "background" aqui inline
    // ganharia do stylesheet e quebraria a troca de tema.
    var t = Math.max(-1, Math.min(1, value / domain));
    var light = t >= 0 ? lerpHex('#f0efec', '#2a78d6', t) : lerpHex('#f0efec', '#e34948', -t);
    var dark = t >= 0 ? lerpHex('#383835', '#3987e5', t) : lerpHex('#383835', '#e66767', -t);
    return '--cell-light:' + light + ';--cell-dark:' + dark + ';';
  }

  function lerpHex(c1, c2, t) {
    var r1 = parseInt(c1.slice(1, 3), 16), g1 = parseInt(c1.slice(3, 5), 16), b1 = parseInt(c1.slice(5, 7), 16);
    var r2 = parseInt(c2.slice(1, 3), 16), g2 = parseInt(c2.slice(3, 5), 16), b2 = parseInt(c2.slice(5, 7), 16);
    var r = Math.round(r1 + (r2 - r1) * t), g = Math.round(g1 + (g2 - g1) * t), b = Math.round(b1 + (b2 - b1) * t);
    return '#' + [r, g, b].map(function(x) { return x.toString(16).padStart(2, '0'); }).join('');
  }

  function computeLab(country) {
    var skeleton = JSON.parse(document.getElementById('lab-skeleton-' + country).textContent);
    var inputs = document.querySelectorAll('#lab-panel-' + country + ' .lab-bps-input');
    var bps = Array.prototype.map.call(inputs, function(el) { return parseFloat(el.value) || 0; });

    // Níveis absolutos acumulados (%), começando na taxa de política atual --
    // caminho ABSOLUTO, não choque relativo ao que o mercado precifica.
    var levels = [];
    var level = skeleton.current_policy_rate_pct;
    for (var i = 0; i < skeleton.meetings.length; i++) {
      level = level + bps[i] / 100;
      levels.push(level);
    }

    var dfs = [1.0];
    for (i = 0; i < skeleton.meetings.length; i++) {
      var m = skeleton.meetings[i];
      dfs.push(dfs[i] * discountFactor(levels[i], m.tau, skeleton.compounding));
    }

    var maxAbsMeetingDelta = 5;
    var meetingRows = skeleton.meetings.map(function(m, i) {
      var marketChangeBps = (m.market_forward_pct - (i === 0 ? skeleton.current_policy_rate_pct : skeleton.meetings[i - 1].market_forward_pct)) * 100;
      var scenarioChangeBps = bps[i];
      var deltaBps = scenarioChangeBps - marketChangeBps;
      maxAbsMeetingDelta = Math.max(maxAbsMeetingDelta, Math.abs(deltaBps));
      return { date: m.date, market_bps: marketChangeBps, scenario_bps: scenarioChangeBps, delta_bps: deltaBps, level_pct: levels[i] };
    });

    var lastLevel = levels[levels.length - 1];
    var lastMarket = skeleton.meetings[skeleton.meetings.length - 1].market_forward_pct;
    var finalShiftPct = lastLevel - lastMarket;

    var maxAbsVertexDelta = 5;
    var vertexRows = skeleton.vertices.map(function(v) {
      var df;
      if (v.segment_index !== null) {
        df = dfs[v.segment_index - 1] * discountFactor(levels[v.segment_index - 1], v.tau_from_segment_start, skeleton.compounding);
      } else {
        var tailRatePct = v.tail_base_forward_pct + finalShiftPct;
        df = dfs[dfs.length - 1] * discountFactor(tailRatePct, v.tail_tau, skeleton.compounding);
      }
      var zeroPct = zeroRatePct(df, v.tau_from_valuation, skeleton.compounding);
      var deltaBps = (zeroPct - v.market_zero_pct) * 100;
      maxAbsVertexDelta = Math.max(maxAbsVertexDelta, Math.abs(deltaBps));
      return { maturity: v.maturity, market_pct: v.market_zero_pct, scenario_pct: zeroPct, delta_bps: deltaBps };
    });

    renderResults(country, meetingRows, vertexRows, maxAbsMeetingDelta, maxAbsVertexDelta);
  }

  function renderResults(country, meetingRows, vertexRows, meetingDomain, vertexDomain) {
    var meetingBody = document.getElementById('lab-meeting-tbody-' + country);
    meetingBody.innerHTML = meetingRows.map(function(r) {
      return '<tr><td class="ink-secondary">' + r.date + '</td>' +
        '<td class="num">' + fmtBps(r.market_bps) + '</td>' +
        '<td class="num">' + fmtBps(r.scenario_bps) + '</td>' +
        '<td class="num heat-cell" style="' + heatStyle(r.delta_bps, meetingDomain) + '">' + fmtBps(r.delta_bps) + '</td>' +
        '<td class="num">' + fmtPct(r.level_pct) + '</td></tr>';
    }).join('');

    var vertexBody = document.getElementById('lab-vertex-tbody-' + country);
    vertexBody.innerHTML = vertexRows.map(function(r) {
      return '<tr><td class="ink-secondary">' + r.maturity + '</td>' +
        '<td class="num">' + fmtPct(r.market_pct) + '</td>' +
        '<td class="num">' + fmtPct(r.scenario_pct) + '</td>' +
        '<td class="num heat-cell" style="' + heatStyle(r.delta_bps, vertexDomain) + '">' + fmtBps(r.delta_bps) + '</td></tr>';
    }).join('');

    document.getElementById('lab-results-' + country).hidden = false;
  }

  function resetLab(country) {
    var inputs = document.querySelectorAll('#lab-panel-' + country + ' .lab-bps-input');
    Array.prototype.forEach.call(inputs, function(el) { el.value = 0; });
    var results = document.getElementById('lab-results-' + country);
    if (results) results.hidden = true;
  }

  document.querySelectorAll('.lab-calc-btn').forEach(function(btn) {
    btn.addEventListener('click', function() { computeLab(btn.getAttribute('data-country')); });
  });
  document.querySelectorAll('.lab-reset-btn').forEach(function(btn) {
    btn.addEventListener('click', function() { resetLab(btn.getAttribute('data-country')); });
  });
  document.querySelectorAll('.lab-tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var country = btn.getAttribute('data-country');
      document.querySelectorAll('.lab-tab-btn').forEach(function(b) { b.classList.remove('lab-tab-active'); });
      document.querySelectorAll('.lab-panel').forEach(function(p) { p.classList.remove('lab-panel-active'); });
      btn.classList.add('lab-tab-active');
      document.getElementById('lab-panel-' + country).classList.add('lab-panel-active');
    });
  });
})();
</script>"""


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

    scenario_sections_html = []
    for c in countries_data:
        section_data = build_scenario_section_data(settings, processed_dir, c["country"], c["label"])
        if section_data is not None:
            scenario_sections_html.append(render_scenario_section(section_data))
    if not scenario_sections_html:
        print("Nenhum cenário em scenarios/<país>/*.yaml (ou Input_BCs.xlsx indisponível) — seção de cenários pulada.")

    lab_data_list = []
    for c in countries_data:
        lab_data = build_lab_section_data(settings, processed_dir, c["country"], c["label"])
        if lab_data is not None:
            lab_data_list.append(lab_data)
    lab_section_html = render_lab_section(lab_data_list)
    if not lab_data_list:
        print("Sem reuniões/curva suficientes pra aba de cenários interativos — seção pulada.")

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
  .scenario-section {{ margin-top: 40px; }}
  .scenario-section h3 {{ font-size: 17px; margin: 0 0 4px; }}
  .scenario-note {{ font-size: 12px; color: var(--ink-muted); margin: 0 0 16px; }}
  .scenario-section h4 {{ font-size: 12px; color: var(--ink-muted); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.02em; margin: 20px 0 8px; }}
  .panel {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; overflow-x: auto; margin-bottom: 8px; }}
  table.compare {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  table.compare th, table.compare td {{ padding: 6px 10px; text-align: right; white-space: nowrap;
    font-variant-numeric: tabular-nums; }}
  table.compare th:first-child, table.compare td:first-child {{ text-align: left; }}
  table.compare th {{ color: var(--ink-muted); font-weight: 500; font-size: 11px; border-bottom: 1px solid var(--gridline); }}
  table.compare td {{ border-bottom: 1px solid var(--gridline); }}
  footer {{ margin-top: 32px; font-size: 11px; color: var(--ink-muted); }}
  .lab-section {{ margin-top: 40px; }}
  .lab-section h3 {{ font-size: 17px; margin: 0 0 4px; }}
  .lab-tabs {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0; }}
  .lab-tab-btn {{
    font: inherit; font-size: 12px; color: var(--ink-secondary); background: var(--surface-1);
    border: 1px solid var(--border); border-radius: 999px; padding: 6px 14px; cursor: pointer;
  }}
  .lab-tab-btn:hover {{ color: var(--ink-primary); border-color: var(--ink-muted); }}
  .lab-tab-btn.lab-tab-active {{ background: var(--diverge-blue); border-color: var(--diverge-blue); color: #fff; }}
  .lab-panel {{ display: none; }}
  .lab-panel.lab-panel-active {{ display: block; }}
  table.lab-input-table {{
    border-collapse: collapse; width: 100%; max-width: 480px; font-size: 13px; margin-bottom: 14px;
  }}
  table.lab-input-table th, table.lab-input-table td {{
    padding: 6px 10px; text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums;
  }}
  table.lab-input-table th:first-child, table.lab-input-table td:first-child {{ text-align: left; }}
  table.lab-input-table th {{ color: var(--ink-muted); font-weight: 500; font-size: 11px; border-bottom: 1px solid var(--gridline); }}
  table.lab-input-table td {{ border-bottom: 1px solid var(--gridline); }}
  .lab-bps-input {{
    width: 72px; font: inherit; font-variant-numeric: tabular-nums; text-align: right;
    background: var(--page); color: var(--ink-primary); border: 1px solid var(--border); border-radius: 6px;
    padding: 4px 8px;
  }}
  .lab-bps-input:focus {{ outline: 2px solid var(--diverge-blue); outline-offset: 1px; }}
  .lab-actions {{ display: flex; gap: 10px; margin-bottom: 20px; }}
  .lab-calc-btn, .lab-reset-btn {{
    font: inherit; font-size: 13px; font-weight: 600; border-radius: 8px; padding: 8px 18px; cursor: pointer; border: 1px solid transparent;
  }}
  .lab-calc-btn {{ background: var(--diverge-blue); color: #fff; }}
  .lab-calc-btn:hover {{ opacity: 0.9; }}
  .lab-reset-btn {{ background: transparent; color: var(--ink-secondary); border-color: var(--border); }}
  .lab-reset-btn:hover {{ color: var(--ink-primary); border-color: var(--ink-muted); }}
  .lab-results h4 {{ font-size: 12px; color: var(--ink-muted); font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.02em; margin: 20px 0 8px; }}
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

  {''.join(scenario_sections_html)}

  {lab_section_html}

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
