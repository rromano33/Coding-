import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { statsApi } from "../api/endpoints";
import type { BreakdownItem, EquityCurvePoint, PerformanceSummary } from "../types";
import { formatCurrency, formatDate, formatNumber, formatPercent, pnlColor } from "../utils/format";
import StatCard from "../components/StatCard";

export default function PerformancePage() {
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [equity, setEquity] = useState<EquityCurvePoint[]>([]);
  const [byStrategy, setByStrategy] = useState<BreakdownItem[]>([]);
  const [byAsset, setByAsset] = useState<BreakdownItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([statsApi.summary(), statsApi.equityCurve(), statsApi.byStrategy(), statsApi.byAsset()]).then(
      ([s, e, st, as]) => {
        setSummary(s);
        setEquity(e);
        setByStrategy(st);
        setByAsset(as);
        setLoading(false);
      }
    );
  }, []);

  if (loading || !summary) return <p className="text-slate-500 text-sm">Carregando...</p>;

  const chartData = equity.map((p) => ({ ...p, dateLabel: formatDate(p.date) }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Performance</h1>

      <div className="grid grid-cols-2 gap-3">
        <StatCard
          label="PnL total"
          value={formatCurrency(summary.total_pnl)}
          accent={summary.total_pnl >= 0 ? "green" : "red"}
        />
        <StatCard label="Win rate" value={formatPercent(summary.win_rate)} />
        <StatCard label="Trades fechados" value={String(summary.closed_trades)} />
        <StatCard label="Trades abertos" value={String(summary.open_trades)} />
        <StatCard label="Expectativa/trade" value={formatCurrency(summary.expectancy)} />
        <StatCard label="R médio" value={summary.avg_r_multiple !== null ? `${formatNumber(summary.avg_r_multiple)}R` : "—"} />
        <StatCard label="Fator de lucro" value={summary.profit_factor !== null ? formatNumber(summary.profit_factor) : "—"} />
        <StatCard label="Drawdown máx." value={formatCurrency(summary.max_drawdown)} accent="red" />
      </div>

      {chartData.length > 1 && (
        <div>
          <h2 className="text-sm font-medium text-slate-300 mb-2">Curva de capital (PnL acumulado)</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="dateLabel" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} minTickGap={30} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={50} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                  formatter={(value: number) => formatCurrency(value)}
                />
                <Area type="monotone" dataKey="cumulative_pnl" stroke="#22c55e" fill="url(#pnlGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <Breakdown title="Por estratégia" items={byStrategy} />
      <Breakdown title="Por ativo" items={byAsset} />
    </div>
  );
}

function Breakdown({ title, items }: { title: string; items: BreakdownItem[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h2 className="text-sm font-medium text-slate-300 mb-2">{title}</h2>
      <div className="bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800">
        {items.map((item) => (
          <div key={item.key} className="flex items-center justify-between px-4 py-2.5 text-sm">
            <div>
              <p className="text-slate-200">{item.key}</p>
              <p className="text-xs text-slate-500">
                {item.trade_count} trades · {formatPercent(item.win_rate)} win
              </p>
            </div>
            <p className={`font-medium ${pnlColor(item.total_pnl)}`}>{formatCurrency(item.total_pnl)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
