"""Gera um HTML autocontido e INTERATIVO: embute o histórico de
preços/taxas (mesma aba "Preços" que alimenta o relatório oficial) de
todos os tickers disponíveis, e cada pessoa da mesa preenche as PRÓPRIAS
posições direto no navegador -- sem Python, sem sessão Bloomberg, sem
enviar planilha nenhuma. VaR histórico/paramétrico, ES, vol e diversificação
recalculam em JavaScript puro a cada posição adicionada ou removida.

Diferença importante em relação a riskvar.html_report (o relatório oficial,
gerado a partir da SUA planilha real):
- Aqui só o HISTÓRICO DE MERCADO (preços/taxas) vem embutido -- nenhuma
  posição de ninguém. Cada pessoa entra com as próprias posições, que
  ficam só no navegador dela (não são salvas, não saem da máquina).
- O arquivo é uma FOTO do mercado no momento em que foi gerado -- não tem
  como se conectar à Bloomberg depois de exportado. Por isso o banner no
  topo do HTML deixa a data da última atualização bem explícita: quem
  receber o arquivo precisa saber até quando os preços valem.
- Escopo intencionalmente menor que o relatório oficial: sem gráfico de
  P&L acumulado nem pizza de contribuição por classe (a tabela de ativos
  tem contribuição % por posição, só não agrupada visualmente por classe
  -- essa ferramenta não pede uma "Classe" no editor de posições). Os
  números de risco em si -- VaR, ES, vol, diversificação, correlação,
  piores dias, stress test -- são os mesmos cálculos do relatório oficial,
  só que rodados em JS em vez de em Python (ver PORT NOTE abaixo pra como
  cada fórmula foi portada e verificada).

PORT NOTE (importante ler antes de mexer no JS deste arquivo): a
matemática (VaR histórico/paramétrico, ES, vol, quebra de estouros,
diversificação, regressão de stress) é uma tradução linha-a-linha de
riskvar/var_metrics.py, riskvar/pnl_series.py e riskvar/stress.py pra
JavaScript -- qualquer mudança de fórmula deve ser feita nos DOIS lados
(Python E JS) e reverificada com scripts/verify_interactive_var.py (compara
saída do JS via Playwright contra riskvar/var_metrics.py num exemplo
sintético determinístico; ver esse script pra tolerância aceita)."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from riskvar.html_report import _CSS, _json_for_script, save_standalone_html

__all__ = ["render_interactive_html", "save_standalone_html"]


def _price_history_payload(price_histories: dict[str, pd.Series], max_days: int) -> dict[str, list[list]]:
    """Uma lista [data ISO, valor] por ticker, mais recente por último --
    só os últimos `max_days` pontos (maior janela configurada + folga),
    não a série completa, pra manter o HTML num tamanho razoável."""
    payload = {}
    for ticker, series in sorted(price_histories.items()):
        trimmed = series.dropna().sort_index().tail(max_days)
        payload[ticker] = [[ts.strftime("%Y-%m-%d"), float(v)] for ts, v in trimmed.items()]
    return payload


def render_interactive_html(
    price_histories: dict[str, pd.Series],
    lookback_windows: dict[str, int],
    confidence_levels: list[float],
    trading_days_per_year: int,
    base_currency: str,
    valuation_date: date,
    generated_at: datetime,
    stress_factors: dict | None = None,
    stress_scenarios: list | None = None,
) -> str:
    max_days = max(lookback_windows.values()) + 5
    price_payload = _price_history_payload(price_histories, max_days)

    config = {
        "lookback_windows": lookback_windows,
        "confidence_levels": confidence_levels,
        "trading_days_per_year": trading_days_per_year,
        "base_currency": base_currency,
        "valuation_date": valuation_date.strftime("%d/%m/%Y"),
        "generated_at": generated_at.strftime("%d/%m/%Y %H:%M"),
        "stress_factors": stress_factors or {},
        "stress_scenarios": stress_scenarios or [],
    }

    n_tickers = len(price_payload)

    body = (
        _CSS
        + _EXTRA_CSS
        + _BODY_TEMPLATE.replace("___VALUATION_DATE___", config["valuation_date"])
        .replace("___GENERATED_AT___", config["generated_at"])
        .replace("___N_TICKERS___", str(n_tickers))
        .replace("___BASE_CURRENCY___", base_currency)
        + "\n<script>\n"
        + f"const PRICE_HISTORY = {_json_for_script(price_payload)};\n"
        + f"const CONFIG = {_json_for_script(config)};\n"
        + _JS_ENGINE
        + "\n</script>\n"
    )
    return body


_EXTRA_CSS = '''
<style>
  .snapshot-banner {
    background: var(--page-plane); border: 1px solid var(--border); border-left: 3px solid var(--series-1);
    border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; font-size: 13px; color: var(--text-secondary);
    line-height: 1.6;
  }
  .snapshot-banner strong { color: var(--text-primary); }
  #positions-tbody input[type=text], #positions-tbody input[type=number], #positions-tbody select {
    font: inherit; font-size: 13px; color: var(--text-primary); background: var(--page-plane);
    border: 1px solid var(--border); border-radius: 4px; padding: 5px 7px; width: 100%; box-sizing: border-box;
  }
  #positions-tbody input[type=number] { text-align: right; }
  #positions-tbody td { vertical-align: middle; }
  .remove-btn {
    font: inherit; font-size: 15px; color: var(--text-muted); background: transparent; border: none;
    cursor: pointer; padding: 2px 10px; line-height: 1;
  }
  .remove-btn:hover { color: var(--delta-critical); }
  .empty-state { color: var(--text-muted); font-size: 13px; padding: 8px 0; }
</style>
'''

_BODY_TEMPLATE = '''
<div class="viz-root">
  <div class="report">
    <div class="report-header">
      <h1>Risco de portfólio — interativo</h1>
      <p>Preencha suas posições abaixo — os números recalculam na hora, direto no navegador.</p>
    </div>

    <div class="snapshot-banner">
      <strong>Dados de mercado até ___VALUATION_DATE___</strong> (gerados em ___GENERATED_AT___, a partir da
      Bloomberg local de quem exportou este arquivo). Este HTML é uma <strong>FOTO estática</strong> — preços e
      taxas ficaram fixos no momento da exportação, o arquivo não se conecta à Bloomberg nem à internet depois
      disso. Pra atualizar os preços, peça uma nova versão gerada depois dessa data. Universo disponível nesta
      foto: ___N_TICKERS___ tickers. Base ___BASE_CURRENCY___.
    </div>

    <section class="card">
      <h2>Suas posições</h2>
      <p class="footer-note" style="margin-top:-8px; margin-bottom:14px;">
        Nenhuma posição fica salva nem sai do seu navegador — ao fechar a aba, some. Escolha o ticker, o tipo
        (Notional = preço/nível; DV01 = taxa/yield cotada em %) e a posição.
      </p>
      <div class="table-scroll">
        <table class="data-table" id="positions-table">
          <thead><tr><th style="width:26%">Ativo</th><th style="width:32%">Ticker</th><th style="width:16%">Tipo</th><th class="num" style="width:18%">Posição</th><th style="width:8%"></th></tr></thead>
          <tbody id="positions-tbody"></tbody>
        </table>
      </div>
      <button type="button" class="ghost-btn" id="add-position-btn" style="margin-top:12px;">+ Adicionar posição</button>
    </section>

    <div id="results-root" hidden>
      <div id="positions-summary-container"></div>
      <div class="stat-grid" id="stat-grid"></div>
      <div id="correlation-container"></div>
      <div id="report-table-container"></div>
      <div id="worst-days-container"></div>
      <div id="stress-container"></div>
    </div>
    <div id="empty-state" class="card"><p class="empty-state">Adicione ao menos uma posição acima pra ver os números de risco.</p></div>

    <p class="footer-note">VaR/ES de 1 dia, histórico e paramétrico (variância-covariância). "Janela" é o
      período de P&amp;L histórico usado para estimar cada métrica, não o horizonte do VaR. Benefício de
      diversificação: 1 - VaR do portfólio / soma dos VaRs de cada posição isolada. Mesmas fórmulas do
      relatório oficial gerado em Python — só que calculadas aqui, no navegador, com as posições que você
      digitou.</p>
  </div>
</div>
'''

# NOTA DE PORTABILIDADE: cada função abaixo é a tradução direta de uma
# função Python equivalente -- ver o docstring do módulo pra onde. Mudou
# uma fórmula de um lado, muda dos dois.
_JS_ENGINE = '''
// ---- estatística básica (porta de riskvar/var_metrics.py) ----
function mean(arr) { return arr.reduce((s, v) => s + v, 0) / arr.length; }
function stdSample(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  const ss = arr.reduce((s, v) => s + (v - m) * (v - m), 0);
  return Math.sqrt(ss / (arr.length - 1));
}
function percentile(sortedArr, p) {
  const n = sortedArr.length;
  if (n === 1) return sortedArr[0];
  const idx = (p / 100) * (n - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return sortedArr[lo];
  return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
}
function normPdf(z) { return Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI); }
function normPpf(p) {
  // Algoritmo racional de Peter Acklam pra inversa da normal padrão --
  // mesma função que scipy.stats.norm.ppf usa internamente em espírito
  // (precisão ~1e-9, mais que suficiente pros quantis de VaR/ES).
  const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
  const b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
  const c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
  const d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
  const pLow = 0.02425, pHigh = 1 - pLow;
  let q, r;
  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
  } else if (p <= pHigh) {
    q = p - 0.5; r = q * q;
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
  } else {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
  }
}
function historicalVar(pnlArr, confidence) {
  const sorted = [...pnlArr].sort((a, b) => a - b);
  return -percentile(sorted, (1 - confidence) * 100);
}
function parametricVar(pnlArr, confidence) {
  const z = normPpf(1 - confidence);
  return -(mean(pnlArr) + z * stdSample(pnlArr));
}
function historicalEs(pnlArr, confidence) {
  const sorted = [...pnlArr].sort((a, b) => a - b);
  const threshold = percentile(sorted, (1 - confidence) * 100);
  let tail = sorted.filter(v => v <= threshold);
  if (tail.length === 0) tail = sorted;
  return -mean(tail);
}
function parametricEs(pnlArr, confidence) {
  const alpha = 1 - confidence, z = normPpf(alpha);
  const esPnl = mean(pnlArr) - stdSample(pnlArr) * normPdf(z) / alpha;
  return -esPnl;
}
function countBreaches(pnlArr, varEstimate) {
  return pnlArr.filter(v => -v > varEstimate).length;
}

// ---- P&L de posição e alinhamento de portfólio (porta de riskvar/pnl_series.py) ----
function positionPnlSeries(position, priceSeries) {
  // priceSeries: [[dataISO, valor], ...] ascendente. Retorna [[dataISO, pnl], ...]
  // notional: retorno % * posição (equivalente a pandas pct_change());
  // dv01: variação em bps (diff * 100) * posição.
  const out = [];
  for (let i = 1; i < priceSeries.length; i++) {
    const v0 = priceSeries[i - 1][1], v1 = priceSeries[i][1];
    const change = position.type === 'notional' ? (v1 - v0) / v0 : (v1 - v0) * 100;
    out.push([priceSeries[i][0], position.value * change]);
  }
  return out;
}
function alignedFrame(seriesList) {
  // seriesList: array de [[dataISO, pnl], ...] (uma por posição). União das
  // datas, preenchendo com 0 onde uma posição não tem P&L naquele dia --
  // mesma convenção de _aligned_position_pnl_frame (pandas concat+fillna(0)).
  const dateSet = new Set();
  seriesList.forEach(s => s.forEach(([d]) => dateSet.add(d)));
  const dates = [...dateSet].sort();
  const maps = seriesList.map(s => new Map(s));
  const columns = maps.map(m => dates.map(d => m.get(d) || 0));
  return { dates, columns };
}
function sumColumns(columns, dates) {
  return dates.map((_, i) => columns.reduce((s, col) => s + col[i], 0));
}
function covarianceSample(a, b) {
  const ma = mean(a), mb = mean(b);
  let s = 0;
  for (let i = 0; i < a.length; i++) s += (a[i] - ma) * (b[i] - mb);
  return s / (a.length - 1);
}
function riskContributionPct(columns, portfolioArr) {
  // porta de risk_contribution_pct: beta_i = Cov(pnl_i, pnl_portfolio) / Var(pnl_portfolio),
  // soma sempre 100% por construção. Fallback pra divisão igual se a
  // variância do portfólio for zero (mesma regra do lado Python).
  const portfolioVarStat = covarianceSample(portfolioArr, portfolioArr);
  if (!portfolioVarStat) return columns.map(() => 100 / columns.length);
  return columns.map(col => (covarianceSample(col, portfolioArr) / portfolioVarStat) * 100);
}
function correlationMatrix(columns) {
  // NxN, porta de correlation_matrix (Pearson do P&L diário entre pares de posições).
  const n = columns.length;
  const stds = columns.map(col => stdSample(col));
  const matrix = Array.from({length: n}, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      matrix[i][j] = (stds[i] && stds[j]) ? covarianceSample(columns[i], columns[j]) / (stds[i] * stds[j]) : (i === j ? 1 : 0);
    }
  }
  return matrix;
}

// ---- regressão multi-fator (porta de riskvar/stress.py) ----
function gaussSolve(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(M[r][col]) > Math.abs(M[pivot][col])) pivot = r;
    [M[col], M[pivot]] = [M[pivot], M[col]];
    const pv = M[col][col];
    if (Math.abs(pv) < 1e-12) continue;
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const factor = M[r][col] / pv;
      for (let c = col; c <= n; c++) M[r][c] -= factor * M[col][c];
    }
  }
  return M.map((row, i) => row[i] ? row[n] / row[i] : 0);
}
function fitFactorSensitivities(pnlArr, factorArrs) {
  // factorArrs: {nome: array alinhado ao pnlArr (mesmo comprimento/ordem)}
  const names = Object.keys(factorArrs);
  const n = pnlArr.length, k = names.length + 1;
  const X = pnlArr.map((_, i) => [1, ...names.map(name => factorArrs[name][i])]);
  const betas = gaussSolve(
    Array.from({length: k}, (_, a) => Array.from({length: k}, (_, b) => X.reduce((s, row) => s + row[a] * row[b], 0))),
    Array.from({length: k}, (_, a) => X.reduce((s, row, i) => s + row[a] * pnlArr[i], 0))
  );
  const yMean = mean(pnlArr);
  let residualSs = 0, totalSs = 0;
  for (let i = 0; i < n; i++) {
    const fitted = X[i].reduce((s, x, a) => s + x * betas[a], 0);
    residualSs += (pnlArr[i] - fitted) ** 2;
    totalSs += (pnlArr[i] - yMean) ** 2;
  }
  const rSquared = totalSs ? 1 - residualSs / totalSs : 0;
  const betaByName = {};
  names.forEach((name, i) => { betaByName[name] = betas[i + 1]; });
  return { betas: betaByName, rSquared };
}

// ---- formatação (mesmo padrão de riskvar/html_report.py) ----
function fmtUsdCompact(value) {
  const sign = value < 0 ? '-' : '';
  const v = Math.abs(value);
  if (v >= 1e9) return sign + '$' + (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return sign + '$' + (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return sign + '$' + (v / 1e3).toFixed(1) + 'K';
  return sign + '$' + v.toLocaleString('en-US', {maximumFractionDigits: 0});
}
function fmtUsdFull(value) {
  return (value < 0 ? '-' : '') + '$' + Math.abs(value).toLocaleString('en-US', {maximumFractionDigits: 0});
}
function fmtPct(value) { return (value * 100).toFixed(0) + '%'; }
function statTile(label, value) {
  return '<div class="stat-tile"><div class="stat-label">' + label + '</div><div class="stat-value">' + value + '</div></div>';
}
function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ---- leitura das posições digitadas na tabela ----
function readPositions() {
  const rows = document.querySelectorAll('#positions-tbody tr');
  const positions = [];
  rows.forEach(row => {
    const ticker = row.querySelector('.pos-ticker').value;
    const rawValue = row.querySelector('.pos-value').value;
    const value = parseFloat(rawValue);
    if (!ticker || !rawValue || !isFinite(value) || value === 0) return; // mesma regra do PortfolioLoader: linha de referência sem posição não entra na conta
    const asset = row.querySelector('.pos-asset').value.trim() || ticker;
    const type = row.querySelector('.pos-type').value;
    positions.push({ asset, ticker, type, value });
  });
  return positions;
}

// ---- pipeline de janela: replica exatamente run_var.py -- tail(n+1) de
// preço por posição, P&L alinhado (união+fillna0) ----
function windowAlignedFrame(positions, nDays) {
  const perPosition = positions.map(pos => {
    const prices = PRICE_HISTORY[pos.ticker].slice(-(nDays + 1));
    return positionPnlSeries(pos, prices);
  });
  return alignedFrame(perPosition);
}
function windowPortfolioPnl(positions, nDays) {
  const { dates, columns } = windowAlignedFrame(positions, nDays);
  const summed = sumColumns(columns, dates);
  const combined = dates.map((d, i) => [d, summed[i]]);
  return combined.slice(-nDays); // tail(n_days) final no resultado somado, mesma dupla-trim de run_var.py
}

function riskMetrics(pnlArr, confidence, tradingDaysPerYear) {
  const dailyVol = stdSample(pnlArr);
  const varHist = historicalVar(pnlArr, confidence);
  const varParam = parametricVar(pnlArr, confidence);
  return {
    confidence, nObs: pnlArr.length,
    varHistorical: varHist, varParametric: varParam,
    esHistorical: historicalEs(pnlArr, confidence), esParametric: parametricEs(pnlArr, confidence),
    dailyVol, annualizedVol: dailyVol * Math.sqrt(tradingDaysPerYear),
    nBreachesHistorical: countBreaches(pnlArr, varHist), nBreachesParametric: countBreaches(pnlArr, varParam),
    expectedBreaches: pnlArr.length * (1 - confidence),
  };
}

// ---- diversificação e VaR individual (porta de diversification_benefit / standalone_var_by_position) ----
function standaloneVarByPosition(columns, confidence) {
  return columns.map(col => historicalVar(col, confidence));
}
function diversificationBenefit(columns, dates, confidence) {
  const standaloneVars = standaloneVarByPosition(columns, confidence);
  const standaloneSum = standaloneVars.reduce((s, v) => s + v, 0);
  const portfolioVar = historicalVar(sumColumns(columns, dates), confidence);
  const benefitPct = standaloneSum ? (1 - portfolioVar / standaloneSum) * 100 : 0;
  return { standaloneSum, portfolioVar, benefitPct };
}

function worstDays(pnlPairs, n) {
  return [...pnlPairs].sort((a, b) => a[1] - b[1]).slice(0, n);
}

// ---- construção do HTML dos resultados ----
function buildStatTiles(byWindow) {
  // Três linhas por MÉTRICA (não por janela): VaR / ES / Vol -- mesmo
  // agrupamento do relatório oficial (_build_stat_tiles em html_report.py).
  const windows = Object.keys(CONFIG.lookback_windows);
  let html = '';
  windows.forEach(window => {
    CONFIG.confidence_levels.forEach(conf => {
      html += statTile('VaR histórico · ' + window + ' · ' + fmtPct(conf), fmtUsdCompact(byWindow[window][conf].varHistorical));
    });
  });
  html += '<div class="stat-break"></div>';
  windows.forEach(window => {
    CONFIG.confidence_levels.forEach(conf => {
      html += statTile('ES histórico · ' + window + ' · ' + fmtPct(conf), fmtUsdCompact(byWindow[window][conf].esHistorical));
    });
  });
  html += '<div class="stat-break"></div>';
  windows.forEach(window => {
    const m0 = byWindow[window][CONFIG.confidence_levels[0]];
    html += statTile('Vol diária · ' + window, fmtUsdCompact(m0.dailyVol));
    html += statTile('Vol anualizada · ' + window, fmtUsdCompact(m0.annualizedVol));
  });
  html += '<div class="stat-break"></div>';
  return html;
}
function buildDiversificationRow(div) {
  return statTile('Soma dos VaRs individuais', fmtUsdCompact(div.standaloneSum)) +
    statTile('VaR do portfólio (net)', fmtUsdCompact(div.portfolioVar)) +
    statTile('Benefício de diversificação', div.benefitPct.toFixed(0) + '%') +
    '<div class="stat-break"></div>';
}
function buildPositionsTable(positions, standaloneVar, contributionsByWindow, windowNames) {
  const rows = positions.map((pos, i) => {
    const windowCells = windowNames.map(w => '<td class="num">' + (contributionsByWindow[w][i] >= 0 ? '+' : '') + contributionsByWindow[w][i].toFixed(1) + '%</td>').join('');
    return '<tr><td>' + escapeHtml(pos.asset) + '</td><td>' + escapeHtml(pos.ticker) + '</td>' +
      '<td>' + (pos.type === 'notional' ? 'NOTIONAL' : 'DV01') + '</td>' +
      '<td class="num">' + fmtUsdCompact(pos.value) + (pos.type === 'dv01' ? '/bp' : '') + '</td>' +
      '<td class="num">' + fmtUsdFull(standaloneVar[i]) + '</td>' + windowCells + '</tr>';
  }).join('');
  const windowHeaders = windowNames.map(w => '<th class="num">' + w + '</th>').join('');
  return '<section class="card"><h2>Ativos do portfólio e contribuição ao risco</h2>' +
    '<div class="table-scroll table-scroll--tall"><table class="data-table data-table--compact"><thead><tr>' +
    '<th>Ativo</th><th>Ticker</th><th>Tipo</th><th class="num">Posição</th><th class="num">VaR individual</th>' +
    windowHeaders + '</tr></thead><tbody>' + rows + '</tbody></table></div>' +
    '<p class="footer-note">VaR individual = VaR histórico da posição isolada (janela/confiança primárias). ' +
    'Contribuição = participação de cada ativo na variância do P&amp;L do portfólio (decomposição de Euler via ' +
    'covariância) — soma sempre 100% dentro de cada janela. Valores negativos reduzem o risco do portfólio (hedge).</p>' +
    '</section>';
}
function buildCorrelationTable(positions, corrMatrix, windowLabel) {
  if (positions.length < 2) return '';
  const header = positions.map(p => '<th class="num">' + escapeHtml(p.asset) + '</th>').join('');
  const rows = positions.map((p, i) => '<tr><td>' + escapeHtml(p.asset) + '</td>' +
    corrMatrix[i].map(v => '<td class="num">' + v.toFixed(2) + '</td>').join('') + '</tr>').join('');
  return '<section class="card"><h2>Correlação entre ativos · ' + windowLabel + '</h2>' +
    '<div class="table-scroll"><table class="data-table data-table--compact"><thead><tr><th></th>' + header + '</tr></thead>' +
    '<tbody>' + rows + '</tbody></table></div>' +
    '<p class="footer-note">Correlação de Pearson do P&amp;L diário entre cada par de posições — a base do ' +
    'benefício de diversificação acima: pares com correlação baixa ou negativa (hedges de verdade) reduzem o ' +
    'risco total do portfólio mais do que a soma simples dos VaRs isolados sugere. Diagonal sempre 1.00.</p></section>';
}
function buildReportTable(byWindow) {
  let rows = '';
  Object.keys(CONFIG.lookback_windows).forEach(window => {
    const metricsByConf = byWindow[window];
    CONFIG.confidence_levels.forEach(conf => {
      const m = metricsByConf[conf];
      rows += '<tr><td>' + window + '</td><td>' + fmtPct(conf) + '</td>' +
        '<td class="num">' + m.nObs + '</td>' +
        '<td class="num">' + fmtUsdFull(m.varHistorical) + '</td>' +
        '<td class="num">' + fmtUsdFull(m.varParametric) + '</td>' +
        '<td class="num">' + fmtUsdFull(m.esHistorical) + '</td>' +
        '<td class="num">' + fmtUsdFull(m.esParametric) + '</td>' +
        '<td class="num">' + fmtUsdFull(m.dailyVol) + '</td>' +
        '<td class="num">' + fmtUsdFull(m.annualizedVol) + '</td>' +
        '<td class="num">' + m.nBreachesHistorical + ' / ' + m.expectedBreaches.toFixed(1) + '</td>' +
        '<td class="num">' + m.nBreachesParametric + ' / ' + m.expectedBreaches.toFixed(1) + '</td></tr>';
    });
  });
  return '<section class="card"><h2>VaR, ES e vol por janela de estimação</h2>' +
    '<div class="table-scroll"><table class="data-table"><thead><tr>' +
    '<th>Janela</th><th>Confiança</th><th>N obs.</th><th>VaR histórico</th><th>VaR paramétrico</th>' +
    '<th>ES histórico</th><th>ES paramétrico</th><th>Vol diária</th><th>Vol anualizada</th>' +
    '<th>Estouros hist. / esperado</th><th>Estouros param. / esperado</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table></div></section>';
}
function buildWorstDaysTable(worst, windowLabel) {
  if (!worst.length) return '';
  const rows = worst.map(([d, pnl]) => '<tr><td>' + d + '</td><td class="num">' + fmtUsdFull(pnl) + '</td></tr>').join('');
  return '<section class="card"><h2>Piores dias · ' + windowLabel + '</h2>' +
    '<div class="table-scroll"><table class="data-table"><thead><tr><th>Data</th><th class="num">P&amp;L</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table></div></section>';
}
function buildStressTable(results) {
  if (!results || !results.length) return '';
  const rows = results.map(r => '<tr><td>' + escapeHtml(r.name) + '</td><td class="num">' + fmtUsdFull(r.impact) +
    '</td><td class="num">' + fmtPct(r.rSquared) + '</td></tr>').join('');
  return '<section class="card"><h2>Stress test — sensibilidade a fatores</h2>' +
    '<div class="table-scroll"><table class="data-table"><thead><tr><th>Cenário</th>' +
    '<th class="num">Impacto no P&amp;L</th><th class="num">R²</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table></div>' +
    '<p class="footer-note">Impacto = sensibilidade histórica (regressão contra os fatores configurados) ' +
    'aplicada ao choque do cenário. R² baixo indica que os fatores configurados explicam pouco do P&amp;L ' +
    'dessas posições.</p></section>';
}

// ---- orquestração ----
function recompute() {
  const positions = readPositions();
  const emptyState = document.getElementById('empty-state');
  const resultsRoot = document.getElementById('results-root');
  const missing = positions.filter(p => !PRICE_HISTORY[p.ticker]);
  if (positions.length === 0) {
    emptyState.hidden = false;
    resultsRoot.hidden = true;
    return;
  }
  emptyState.hidden = true;
  resultsRoot.hidden = false;

  const windowNames = Object.keys(CONFIG.lookback_windows);
  const primaryWindow = windowNames.reduce((a, b) => CONFIG.lookback_windows[a] >= CONFIG.lookback_windows[b] ? a : b);
  const primaryConfidence = CONFIG.confidence_levels[0];

  const byWindow = {};
  const pnlPairsByWindow = {};
  const contributionsByWindow = {};
  let primaryFrame = null;
  windowNames.forEach(window => {
    const nDays = CONFIG.lookback_windows[window];
    const frame = windowAlignedFrame(positions, nDays);
    if (window === primaryWindow) primaryFrame = frame;
    const summed = sumColumns(frame.columns, frame.dates);
    const pairs = frame.dates.map((d, i) => [d, summed[i]]).slice(-nDays);
    pnlPairsByWindow[window] = pairs;
    contributionsByWindow[window] = riskContributionPct(frame.columns, summed);
    const pnlArr = pairs.map(p => p[1]);
    const metricsByConf = {};
    CONFIG.confidence_levels.forEach(conf => { metricsByConf[conf] = riskMetrics(pnlArr, conf, CONFIG.trading_days_per_year); });
    byWindow[window] = metricsByConf;
  });

  const primaryNDays = CONFIG.lookback_windows[primaryWindow];
  const standaloneVar = standaloneVarByPosition(primaryFrame.columns, primaryConfidence);
  const div = diversificationBenefit(primaryFrame.columns, primaryFrame.dates, primaryConfidence);
  const corrMatrix = correlationMatrix(primaryFrame.columns);
  const worst = worstDays(pnlPairsByWindow[primaryWindow], 10);

  document.getElementById('positions-summary-container').innerHTML =
    buildPositionsTable(positions, standaloneVar, contributionsByWindow, windowNames);
  let statTilesHtml = buildStatTiles(byWindow);
  statTilesHtml += buildDiversificationRow(div);
  document.getElementById('stat-grid').innerHTML = statTilesHtml;
  document.getElementById('correlation-container').innerHTML = buildCorrelationTable(positions, corrMatrix, primaryWindow);
  document.getElementById('report-table-container').innerHTML = buildReportTable(byWindow);
  document.getElementById('worst-days-container').innerHTML = buildWorstDaysTable(worst, primaryWindow);

  const factorNames = Object.keys(CONFIG.stress_factors || {});
  let stressHtml = '';
  if (factorNames.length && CONFIG.stress_scenarios && CONFIG.stress_scenarios.length) {
    const primaryPairs = pnlPairsByWindow[primaryWindow];
    const primaryDates = primaryPairs.map(p => p[0]);
    const pnlByDate = new Map(primaryPairs);
    const factorArrsAligned = {};
    let ok = true;
    factorNames.forEach(name => {
      const cfg = CONFIG.stress_factors[name];
      const series = PRICE_HISTORY[cfg.ticker];
      if (!series) { ok = false; return; }
      const trimmed = series.slice(-(primaryNDays + 1));
      const changeSeries = positionPnlSeries({ type: cfg.kind === 'pct_return' ? 'notional' : 'dv01', value: 1 }, trimmed);
      factorArrsAligned[name] = new Map(changeSeries);
    });
    if (ok) {
      const commonDates = primaryDates.filter(d => factorNames.every(name => factorArrsAligned[name].has(d)));
      if (commonDates.length >= factorNames.length + 2) {
        const pnlAligned = commonDates.map(d => pnlByDate.get(d));
        const factorArrsFinal = {};
        factorNames.forEach(name => { factorArrsFinal[name] = commonDates.map(d => factorArrsAligned[name].get(d)); });
        const { betas, rSquared } = fitFactorSensitivities(pnlAligned, factorArrsFinal);
        const results = CONFIG.stress_scenarios.map(scenario => {
          let impact = 0;
          Object.keys(scenario.shocks).forEach(factor => { impact += (betas[factor] || 0) * scenario.shocks[factor]; });
          return { name: scenario.name, impact, rSquared };
        });
        stressHtml = buildStressTable(results);
      }
    }
  }
  document.getElementById('stress-container').innerHTML = stressHtml;
}

// ---- editor de posições ----
function tickerOptions() {
  return '<option value="">-- selecione --</option>' + Object.keys(PRICE_HISTORY).sort()
    .map(t => '<option value="' + escapeHtml(t) + '">' + escapeHtml(t) + '</option>').join('');
}
function addPositionRow() {
  const tbody = document.getElementById('positions-tbody');
  const tr = document.createElement('tr');
  tr.innerHTML =
    '<td><input type="text" class="pos-asset" placeholder="Nome (opcional)"></td>' +
    '<td><select class="pos-ticker">' + tickerOptions() + '</select></td>' +
    '<td><select class="pos-type"><option value="notional">Notional</option><option value="dv01">DV01</option></select></td>' +
    '<td class="num"><input type="number" class="pos-value" step="any" placeholder="0"></td>' +
    '<td><button type="button" class="remove-btn" title="Remover">×</button></td>';
  tbody.appendChild(tr);
  tr.querySelector('.remove-btn').addEventListener('click', function () { tr.remove(); recompute(); });
  tr.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', recompute);
    el.addEventListener('input', debouncedRecompute);
  });
}
let debounceTimer = null;
function debouncedRecompute() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(recompute, 250);
}

document.getElementById('add-position-btn').addEventListener('click', addPositionRow);
addPositionRow();
recompute();
'''
