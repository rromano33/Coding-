import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { riskSettingsApi, tradesApi } from "../api/endpoints";
import {
  CONVICTIONS,
  DEFAULT_RISK_CLASS_BY_MARKET,
  MARKETS,
  RISK_CLASSES,
  type ConvictionTier,
  type TradeInput,
} from "../types";
import { formatCurrency, formatNumber, toLocalInputValue } from "../utils/format";

const EMPTY: TradeInput = {
  asset: "",
  market: "acoes",
  direction: "long",
  status: "open",
  entry_date: new Date().toISOString(),
  entry_price: 0,
  exit_date: null,
  exit_price: null,
  quantity: 0,
  stop_price: null,
  target_price: null,
  fees: 0,
  strategy: "",
  tags: "",
  thesis: "",
  notes: "",
  emotions: "",
  conviction: null,
  vol_diaria_pct: null,
  currency: "BRL",
  fx_rate_to_brl: null,
  contract_multiplier: 1,
  risk_class: DEFAULT_RISK_CLASS_BY_MARKET.acoes,
  manual_adjustment: 0,
};

function labelsForMarket(market: string) {
  if (market === "fx") {
    return {
      quantity: "Notional (moeda base)",
      entryPrice: "Taxa de entrada",
      exitPrice: "Taxa de saída",
      showMultiplier: false,
      multiplierLabel: "",
    };
  }
  if (market === "opcoes") {
    return {
      quantity: "Quantidade (contratos)",
      entryPrice: "Prêmio de entrada",
      exitPrice: "Prêmio de saída",
      showMultiplier: true,
      multiplierLabel: "Multiplicador (ações por contrato)",
    };
  }
  if (market === "futuros") {
    return {
      quantity: "Quantidade (contratos)",
      entryPrice: "Pontos de entrada",
      exitPrice: "Pontos de saída",
      showMultiplier: true,
      multiplierLabel: "Multiplicador (valor por ponto)",
    };
  }
  return {
    quantity: "Quantidade",
    entryPrice: "Preço de entrada",
    exitPrice: "Preço de saída",
    showMultiplier: false,
    multiplierLabel: "",
  };
}

export default function TradeFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const [form, setForm] = useState<TradeInput>(EMPTY);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tiers, setTiers] = useState<ConvictionTier[]>([]);

  useEffect(() => {
    riskSettingsApi.listConvictionTiers().then(setTiers);
  }, []);

  useEffect(() => {
    if (!id) return;
    tradesApi.get(Number(id)).then((trade) => {
      setForm({ ...trade });
      setLoading(false);
    });
  }, [id]);

  const labels = labelsForMarket(form.market);
  const isForeignCurrency = Boolean(form.currency && form.currency.trim().toUpperCase() !== "BRL");
  const fxRate = isForeignCurrency ? form.fx_rate_to_brl : 1;
  const multiplier = form.contract_multiplier || 1;

  const selectedTier = tiers.find((t) => t.label === form.conviction) ?? null;
  const riskDistance = form.stop_price !== null ? Math.abs(form.entry_price - form.stop_price) : null;
  const riskPerUnitBRL = riskDistance !== null && fxRate ? riskDistance * multiplier * fxRate : null;
  const suggestedQuantityStop =
    selectedTier && riskPerUnitBRL && riskPerUnitBRL > 0 ? Math.floor(selectedTier.risco_maximo / riskPerUnitBRL) : null;

  const volAmount = form.vol_diaria_pct && form.entry_price ? form.entry_price * (form.vol_diaria_pct / 100) : null;
  const volAmountBRL = volAmount !== null && fxRate ? volAmount * multiplier * fxRate : null;
  const suggestedQuantityVol =
    selectedTier && volAmountBRL && volAmountBRL > 0 ? Math.floor(selectedTier.risco_maximo / volAmountBRL) : null;

  function field<K extends keyof TradeInput>(key: K) {
    return {
      value: (form[key] ?? "") as string | number,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const raw = e.target.value;
        const isNumeric = [
          "entry_price",
          "exit_price",
          "quantity",
          "stop_price",
          "target_price",
          "fees",
          "vol_diaria_pct",
          "fx_rate_to_brl",
          "contract_multiplier",
          "manual_adjustment",
        ].includes(key as string);
        setForm((f) => ({ ...f, [key]: isNumeric ? (raw === "" ? null : Number(raw)) : raw }));
      },
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const payload: TradeInput = {
        ...form,
        entry_date: new Date(form.entry_date).toISOString(),
        exit_date: form.exit_date ? new Date(form.exit_date).toISOString() : null,
      };
      if (isEdit) {
        await tradesApi.update(Number(id), payload);
        navigate(`/trades/${id}`);
      } else {
        const created = await tradesApi.create(payload);
        navigate(`/trades/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar trade");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-slate-500 text-sm">Carregando...</p>;

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">{isEdit ? "Editar trade" : "Novo trade"}</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Ativo</label>
            <input required placeholder="PETR4" {...field("asset")} />
          </div>
          <div>
            <label>Mercado</label>
            <select
              value={form.market}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  market: e.target.value,
                  risk_class: DEFAULT_RISK_CLASS_BY_MARKET[e.target.value] ?? f.risk_class,
                }))
              }
            >
              {MARKETS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Direção</label>
            <select {...field("direction")}>
              <option value="long">Compra (long)</option>
              <option value="short">Venda (short)</option>
            </select>
          </div>
          <div>
            <label>{labels.quantity}</label>
            <input type="number" step="any" required {...field("quantity")} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Moeda</label>
            <input placeholder="BRL, USD, JPY..." {...field("currency")} />
          </div>
          {isForeignCurrency && (
            <div>
              <label>Taxa de conversão pra R$</label>
              <input type="number" step="any" placeholder="ex: 5.42" {...field("fx_rate_to_brl")} />
            </div>
          )}
          {labels.showMultiplier && (
            <div>
              <label>{labels.multiplierLabel}</label>
              <input type="number" step="any" {...field("contract_multiplier")} />
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <label>Data de entrada</label>
            <input
              type="datetime-local"
              required
              value={toLocalInputValue(form.entry_date)}
              onChange={(e) => setForm((f) => ({ ...f, entry_date: e.target.value }))}
            />
          </div>
          <div>
            <label>{labels.entryPrice}</label>
            <input type="number" step="any" required {...field("entry_price")} />
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label>Data de saída</label>
            <input
              type="datetime-local"
              value={toLocalInputValue(form.exit_date)}
              onChange={(e) => setForm((f) => ({ ...f, exit_date: e.target.value || null }))}
            />
          </div>
          <div>
            <label>{labels.exitPrice}</label>
            <input type="number" step="any" {...field("exit_price")} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label>Stop</label>
            <input type="number" step="any" {...field("stop_price")} />
          </div>
          <div>
            <label>Alvo</label>
            <input type="number" step="any" {...field("target_price")} />
          </div>
          <div>
            <label>Taxas/custos</label>
            <input type="number" step="any" {...field("fees")} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Ajuste manual (R$, scaling intraday)</label>
            <input type="number" step="any" {...field("manual_adjustment")} />
          </div>
          <div>
            <label>Classe de risco (p/ diário)</label>
            <select {...field("risk_class")}>
              {RISK_CLASSES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Convicção</label>
            <select
              value={form.conviction ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, conviction: (e.target.value || null) as TradeInput["conviction"] }))}
            >
              <option value="">Sem convicção definida</option>
              {CONVICTIONS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Vol diária estimada (%)</label>
            <input type="number" step="any" placeholder="ex: 2" {...field("vol_diaria_pct")} />
          </div>
        </div>

        {selectedTier && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2.5 text-xs text-slate-400 space-y-2">
            <p>
              Risco máximo para convicção <span className="text-slate-200">{selectedTier.label}</span>:{" "}
              <span className="text-slate-200">{formatCurrency(selectedTier.risco_maximo)}</span>
            </p>

            {isForeignCurrency && !fxRate && (
              <p className="text-amber-400">
                Preencha a taxa de conversão pra R$ pra calcular o sizing sugerido nessa moeda.
              </p>
            )}

            {suggestedQuantityStop !== null ? (
              <div className="flex items-center justify-between">
                <span>
                  Sugestão pelo stop: <span className="text-slate-200">{formatNumber(suggestedQuantityStop, 0)}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, quantity: suggestedQuantityStop }))}
                  className="text-green-400"
                >
                  usar
                </button>
              </div>
            ) : (
              <p>Defina entrada e stop para a sugestão por distância ao stop.</p>
            )}

            {suggestedQuantityVol !== null ? (
              <div className="flex items-center justify-between">
                <span>
                  Sugestão pela vol do ativo: <span className="text-slate-200">{formatNumber(suggestedQuantityVol, 0)}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, quantity: suggestedQuantityVol }))}
                  className="text-green-400"
                >
                  usar
                </button>
              </div>
            ) : (
              <p>Preencha a vol diária estimada para a sugestão baseada em volatilidade (1x vol diária = risco máximo).</p>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label>Estratégia/setup</label>
            <input placeholder="rompimento, pullback..." {...field("strategy")} />
          </div>
          <div>
            <label>Tags</label>
            <input placeholder="separadas, por, vírgula" {...field("tags")} />
          </div>
        </div>

        <div>
          <label>Tese / racional de entrada</label>
          <textarea rows={3} {...field("thesis")} />
        </div>

        <div>
          <label>Análise ex-post / notas</label>
          <textarea rows={3} {...field("notes")} />
        </div>

        <div>
          <label>Estado emocional</label>
          <input placeholder="confiante, ansioso, impulsivo..." {...field("emotions")} />
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg"
        >
          {saving ? "Salvando..." : "Salvar trade"}
        </button>
      </form>
    </div>
  );
}
