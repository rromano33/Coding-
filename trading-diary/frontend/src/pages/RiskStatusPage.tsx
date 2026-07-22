import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { riskApi, riskSettingsApi } from "../api/endpoints";
import type { RiskSettings, RiskStatus, SeasonalPosture } from "../types";
import { formatCurrency, formatPercent, pnlColor } from "../utils/format";
import StatCard from "../components/StatCard";

export default function RiskStatusPage() {
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [settings, setSettings] = useState<RiskSettings | null>(null);
  const [postures, setPostures] = useState<SeasonalPosture[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRules, setShowRules] = useState(false);
  const [showPostures, setShowPostures] = useState(false);

  useEffect(() => {
    Promise.all([riskApi.status(), riskSettingsApi.get(), riskSettingsApi.listSeasonalPostures()]).then(
      ([s, cfg, po]) => {
        setStatus(s);
        setSettings(cfg);
        setPostures(po);
        setLoading(false);
      }
    );
  }, []);

  if (loading || !status || !settings) return <p className="text-slate-500 text-sm">Carregando...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Risco</h1>
        <Link to="/risco/opcoes" className="text-sm text-green-400">
          ⚙ Opções
        </Link>
      </div>

      {status.alerts.length > 0 && (
        <div className="space-y-2">
          {status.alerts.map((alert, i) => {
            const className = `block rounded-lg px-3 py-2.5 text-sm border ${
              alert.severity === "stop"
                ? "bg-red-950/60 border-red-800 text-red-300"
                : "bg-amber-950/40 border-amber-800 text-amber-300"
            }`;
            const content = (
              <>
                <span className="font-medium">{alert.severity === "stop" ? "STOP — " : "Alerta — "}</span>
                {alert.message}
                {alert.trade_id !== null && <span className="ml-1 underline">ver trade →</span>}
              </>
            );
            return alert.trade_id !== null ? (
              <Link key={i} to={`/trades/${alert.trade_id}`} className={className}>
                {content}
              </Link>
            ) : (
              <div key={i} className={className}>
                {content}
              </div>
            );
          })}
        </div>
      )}
      {status.alerts.length === 0 && (
        <div className="rounded-lg px-3 py-2.5 text-sm border bg-green-950/40 border-green-800 text-green-300">
          Nenhum limite de risco violado no momento.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="PnL hoje" value={formatCurrency(status.pnl_today)} accent={status.pnl_today >= 0 ? "green" : "red"} />
        <StatCard label="PnL mês" value={formatCurrency(status.pnl_month)} accent={status.pnl_month >= 0 ? "green" : "red"} />
        <StatCard label="PnL ano" value={formatCurrency(status.pnl_year)} accent={status.pnl_year >= 0 ? "green" : "red"} />
        <StatCard label="% da meta anual" value={formatPercent(status.pct_of_budget_year)} />
      </div>

      <div>
        <h2 className="text-sm font-medium text-slate-300 mb-2">Drawdown do ano</h2>
        <div className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-sm space-y-1">
          <Row label="Drawdown atual" value={formatCurrency(status.drawdown_atual)} />
          <Row
            label="Permitido na fase"
            value={status.drawdown_permitido !== null ? formatCurrency(status.drawdown_permitido) : "—"}
          />
          <Row label="Fase de PnL construído" value={status.drawdown_phase_label ?? "—"} />
          <Row label="Floor mínimo" value={status.drawdown_floor_minimo !== null ? formatCurrency(status.drawdown_floor_minimo) : "—"} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatCard
          label="Trades abertos"
          value={`${status.trades_abertos} / ${status.max_trades_simultaneos}`}
          accent={status.trades_abertos > status.max_trades_simultaneos ? "red" : "neutral"}
        />
        <StatCard
          label="Teses abertas"
          value={`${status.teses_abertas} / ${status.max_teses_simultaneas}`}
          accent={status.teses_abertas > status.max_teses_simultaneas ? "red" : "neutral"}
        />
      </div>

      <Concentration title="Concentração por tese" items={status.concentracao_tese} />
      <Concentration title="Concentração por classe" items={status.concentracao_classe} />

      <div>
        <button
          onClick={() => setShowRules((v) => !v)}
          className="text-sm text-slate-300 flex items-center gap-1 mb-2"
        >
          {showRules ? "▾" : "▸"} Regras comportamentais
        </button>
        {showRules && (
          <ol className="bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800 text-sm list-decimal list-inside">
            {settings.behavioral_rules.map((rule, i) => (
              <li key={i} className="px-4 py-2.5 text-slate-300">
                {rule}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div>
        <button
          onClick={() => setShowPostures((v) => !v)}
          className="text-sm text-slate-300 flex items-center gap-1 mb-2"
        >
          {showPostures ? "▾" : "▸"} Postura sazonal (referência)
        </button>
        {showPostures && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800 text-sm">
            {postures.map((p) => (
              <div key={p.id} className="px-4 py-2.5">
                <p className="text-slate-200">
                  {p.periodo} · {p.situacao_pnl}
                </p>
                <p className="text-slate-500 text-xs mt-0.5">{p.postura}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200">{value}</span>
    </div>
  );
}

function Concentration({ title, items }: { title: string; items: RiskStatus["concentracao_tese"] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h2 className="text-sm font-medium text-slate-300 mb-2">{title}</h2>
      <div className="bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800">
        {items.map((item) => (
          <div key={item.key} className="px-4 py-2.5 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-200">{item.key}</span>
              <span className={item.over ? "text-red-400 font-medium" : pnlColor(0)}>
                {formatCurrency(item.risco_atual)} / {formatCurrency(item.limite)}
              </span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full mt-1.5 overflow-hidden">
              <div
                className={`h-full ${item.over ? "bg-red-500" : "bg-green-500"}`}
                style={{ width: `${Math.min(100, (item.risco_atual / item.limite) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
