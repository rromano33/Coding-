import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { tradesApi } from "../api/endpoints";
import type { Trade } from "../types";
import { formatCurrency, formatDateTime, formatNumber, pnlColor } from "../utils/format";
import { MARKETS, RISK_CLASSES } from "../types";

export default function TradeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [trade, setTrade] = useState<Trade | null>(null);
  const [priceInput, setPriceInput] = useState("");
  const [updatingPrice, setUpdatingPrice] = useState(false);

  useEffect(() => {
    if (!id) return;
    tradesApi.get(Number(id)).then((t) => {
      setTrade(t);
      setPriceInput(t.current_price !== null ? String(t.current_price) : "");
    });
  }, [id]);

  async function handleDelete() {
    if (!trade) return;
    if (!confirm(`Excluir o trade de ${trade.asset}? Essa ação não pode ser desfeita.`)) return;
    await tradesApi.remove(trade.id);
    navigate("/");
  }

  async function handleUpdatePrice(e: React.FormEvent) {
    e.preventDefault();
    if (!trade || priceInput === "") return;
    setUpdatingPrice(true);
    try {
      const updated = await tradesApi.updatePrice(trade.id, Number(priceInput));
      setTrade(updated);
    } finally {
      setUpdatingPrice(false);
    }
  }

  if (!trade) return <p className="text-slate-500 text-sm">Carregando...</p>;

  const marketLabel = MARKETS.find((m) => m.value === trade.market)?.label ?? trade.market;
  const riskClassLabel = RISK_CLASSES.find((c) => c.value === trade.risk_class)?.label ?? null;
  const isForeignCurrency = Boolean(trade.currency && trade.currency.trim().toUpperCase() !== "BRL");

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">
          {trade.asset}{" "}
          <span
            className={`text-xs px-1.5 py-0.5 rounded align-middle ${
              trade.direction === "long" ? "bg-green-600/20 text-green-400" : "bg-red-600/20 text-red-400"
            }`}
          >
            {trade.direction === "long" ? "COMPRA" : "VENDA"}
          </span>
          {trade.stop_alert && (
            <span
              className={`text-xs px-1.5 py-0.5 rounded align-middle ml-1 ${
                trade.stop_alert === "atingido" ? "bg-red-600/20 text-red-400" : "bg-amber-600/20 text-amber-400"
              }`}
            >
              {trade.stop_alert === "atingido" ? "STOP ATINGIDO" : "PERTO DO STOP"}
            </span>
          )}
        </h1>
        <Link to={`/trades/${trade.id}/edit`} className="text-sm text-green-400">
          Editar
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-3">
          <p className="text-xs text-slate-500 mb-1">{trade.status === "open" ? "PnL aberto" : "Resultado"}</p>
          <p className={`text-lg font-semibold ${pnlColor(trade.status === "open" ? trade.unrealized_pnl : trade.pnl)}`}>
            {trade.status === "open"
              ? trade.unrealized_pnl !== null
                ? formatCurrency(trade.unrealized_pnl)
                : "sem marcação"
              : formatCurrency(trade.pnl)}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-3">
          <p className="text-xs text-slate-500 mb-1">Múltiplo R</p>
          <p className="text-lg font-semibold">{trade.r_multiple !== null ? `${formatNumber(trade.r_multiple)}R` : "—"}</p>
        </div>
      </div>

      {trade.status === "open" && (
        <form onSubmit={handleUpdatePrice} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 mb-4">
          <label>Marcar preço atual</label>
          <div className="flex gap-2">
            <input
              type="number"
              step="any"
              placeholder={trade.stop_price !== null ? `stop em ${formatNumber(trade.stop_price)}` : "preço"}
              value={priceInput}
              onChange={(e) => setPriceInput(e.target.value)}
            />
            <button
              type="submit"
              disabled={updatingPrice || priceInput === ""}
              className="shrink-0 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium px-4 rounded-lg"
            >
              {updatingPrice ? "..." : "Marcar"}
            </button>
          </div>
          {trade.current_price !== null && (
            <p className="text-xs text-slate-500 mt-2">
              Última marcação: {formatNumber(trade.current_price)} em {formatDateTime(trade.current_price_updated_at)}
            </p>
          )}
        </form>
      )}

      <dl className="bg-slate-900 border border-slate-800 rounded-xl divide-y divide-slate-800 text-sm mb-4">
        <Row label="Mercado" value={marketLabel} />
        <Row label="Status" value={trade.status === "open" ? "Aberto" : "Fechado"} />
        <Row label="Entrada" value={`${formatDateTime(trade.entry_date)} · ${formatNumber(trade.entry_price)}`} />
        <Row
          label="Saída"
          value={trade.exit_date ? `${formatDateTime(trade.exit_date)} · ${formatNumber(trade.exit_price)}` : "—"}
        />
        <Row label="Quantidade" value={formatNumber(trade.quantity, 0)} />
        <Row label="Stop" value={trade.stop_price !== null ? formatNumber(trade.stop_price) : "—"} />
        <Row label="Alvo" value={trade.target_price !== null ? formatNumber(trade.target_price) : "—"} />
        <Row label="Taxas" value={formatCurrency(trade.fees)} />
        {isForeignCurrency && (
          <>
            <Row label="Moeda" value={trade.currency!} />
            <Row
              label="Taxa de conversão pra R$"
              value={trade.fx_rate_to_brl !== null ? formatNumber(trade.fx_rate_to_brl) : "—"}
            />
          </>
        )}
        {trade.contract_multiplier !== 1 && (
          <Row label="Multiplicador" value={formatNumber(trade.contract_multiplier)} />
        )}
        {trade.manual_adjustment !== 0 && (
          <Row label="Ajuste manual" value={formatCurrency(trade.manual_adjustment)} />
        )}
        <Row label="Classe de risco" value={riskClassLabel ?? "—"} />
        <Row label="Estratégia" value={trade.strategy || "—"} />
        <Row label="Convicção" value={trade.conviction || "—"} />
        <Row label="Tags" value={trade.tags || "—"} />
        <Row label="Estado emocional" value={trade.emotions || "—"} />
      </dl>

      {trade.thesis && (
        <div className="mb-4">
          <h2 className="text-sm font-medium text-slate-300 mb-1">Tese de entrada</h2>
          <p className="text-sm text-slate-400 whitespace-pre-wrap">{trade.thesis}</p>
        </div>
      )}

      {trade.notes && (
        <div className="mb-4">
          <h2 className="text-sm font-medium text-slate-300 mb-1">Análise ex-post</h2>
          <p className="text-sm text-slate-400 whitespace-pre-wrap">{trade.notes}</p>
        </div>
      )}

      <button onClick={handleDelete} className="text-red-400 text-sm mt-2">
        Excluir trade
      </button>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200 text-right">{value}</span>
    </div>
  );
}
