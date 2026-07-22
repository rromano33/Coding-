import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { tradesApi } from "../api/endpoints";
import type { Trade } from "../types";
import { formatCurrency, formatDate, pnlColor } from "../utils/format";

type FilterStatus = "all" | "open" | "closed";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    tradesApi
      .list(filter === "all" ? undefined : { status: filter })
      .then(setTrades)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Trades</h1>
        <Link
          to="/trades/new"
          className="bg-green-600 hover:bg-green-500 text-white text-sm font-medium px-3 py-2 rounded-lg"
        >
          + Novo trade
        </Link>
      </div>

      <div className="flex gap-2 mb-4">
        {(["all", "open", "closed"] as FilterStatus[]).map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-full text-xs border ${
              filter === s
                ? "bg-green-600/20 border-green-600 text-green-400"
                : "border-slate-800 text-slate-400"
            }`}
          >
            {s === "all" ? "Todos" : s === "open" ? "Abertos" : "Fechados"}
          </button>
        ))}
      </div>

      {loading && <p className="text-slate-500 text-sm">Carregando...</p>}
      {!loading && trades.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-12">Nenhum trade registrado ainda.</p>
      )}

      <div className="space-y-2">
        {trades.map((trade) => (
          <Link
            key={trade.id}
            to={`/trades/${trade.id}`}
            className="block bg-slate-900 border border-slate-800 rounded-xl px-4 py-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-100">
                  {trade.asset}{" "}
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${
                      trade.direction === "long"
                        ? "bg-green-600/20 text-green-400"
                        : "bg-red-600/20 text-red-400"
                    }`}
                  >
                    {trade.direction === "long" ? "COMPRA" : "VENDA"}
                  </span>
                  {trade.stop_alert && (
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ml-1 ${
                        trade.stop_alert === "atingido" ? "bg-red-600/20 text-red-400" : "bg-amber-600/20 text-amber-400"
                      }`}
                    >
                      {trade.stop_alert === "atingido" ? "STOP" : "perto do stop"}
                    </span>
                  )}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {formatDate(trade.entry_date)} · {trade.strategy || "sem estratégia"}
                </p>
              </div>
              <div className="text-right">
                {trade.status === "open" ? (
                  trade.unrealized_pnl !== null ? (
                    <p className={`font-semibold ${pnlColor(trade.unrealized_pnl)}`}>{formatCurrency(trade.unrealized_pnl)}</p>
                  ) : (
                    <span className="text-xs text-amber-400">aberto</span>
                  )
                ) : (
                  <p className={`font-semibold ${pnlColor(trade.pnl)}`}>{formatCurrency(trade.pnl)}</p>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
