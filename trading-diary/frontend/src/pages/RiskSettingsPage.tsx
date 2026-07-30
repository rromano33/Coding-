import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { pushApi, riskSettingsApi } from "../api/endpoints";
import {
  disablePushNotifications,
  enablePushNotifications,
  getPushSubscriptionStatus,
  isPushSupported,
} from "../push";
import type {
  ConvictionTierInput,
  DrawdownPhaseInput,
  RiskSettingsInput,
  SeasonalPostureInput,
  StopLayerInput,
} from "../types";
import { formatCurrency } from "../utils/format";

const EMPTY_SETTINGS: RiskSettingsInput = {
  capital_alocado: 0,
  budget_anual_pnl: 0,
  sharpe_meta: 1,
  stop_loss_anual: 0,
  stop_loss_mensal: 0,
  stop_loss_diario: 0,
  risco_max_tese: 0,
  risco_max_classe: 0,
  max_trades_simultaneos: 5,
  max_teses_simultaneas: 3,
};

export default function RiskSettingsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [settings, setSettings] = useState<RiskSettingsInput>(EMPTY_SETTINGS);
  const [volAnual, setVolAnual] = useState(0);
  const [volDiaria, setVolDiaria] = useState(0);
  const [rules, setRules] = useState<string[]>([]);
  const [tiers, setTiers] = useState<ConvictionTierInput[]>([]);
  const [layers, setLayers] = useState<StopLayerInput[]>([]);
  const [phases, setPhases] = useState<DrawdownPhaseInput[]>([]);
  const [postures, setPostures] = useState<SeasonalPostureInput[]>([]);

  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMessage, setPushMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isPushSupported()) return;
    getPushSubscriptionStatus().then((sub) => setPushEnabled(!!sub));
  }, []);

  async function handleTogglePush() {
    setPushBusy(true);
    setPushMessage(null);
    try {
      if (pushEnabled) {
        await disablePushNotifications();
        setPushEnabled(false);
      } else {
        await enablePushNotifications();
        setPushEnabled(true);
      }
    } catch (err) {
      setPushMessage(err instanceof Error ? err.message : "Erro ao configurar notificações");
    } finally {
      setPushBusy(false);
    }
  }

  async function handleTestPush() {
    setPushBusy(true);
    setPushMessage(null);
    try {
      await pushApi.test();
      setPushMessage("Notificação de teste enviada.");
    } catch (err) {
      setPushMessage(err instanceof Error ? err.message : "Erro ao enviar teste");
    } finally {
      setPushBusy(false);
    }
  }

  useEffect(() => {
    Promise.all([
      riskSettingsApi.get(),
      riskSettingsApi.listConvictionTiers(),
      riskSettingsApi.listStopLayers(),
      riskSettingsApi.listDrawdownPhases(),
      riskSettingsApi.listSeasonalPostures(),
    ]).then(([s, t, l, p, po]) => {
      setSettings(s);
      setVolAnual(s.vol_anual);
      setVolDiaria(s.vol_diaria);
      setRules(s.behavioral_rules);
      setTiers(t);
      setLayers(l);
      setPhases(p);
      setPostures(po);
      setLoading(false);
    });
  }, []);

  function numField(setter: (v: RiskSettingsInput) => void, key: keyof RiskSettingsInput) {
    return {
      value: settings[key] ?? 0,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        setter({ ...settings, [key]: Number(e.target.value) });
      },
    };
  }

  async function handleSaveAll() {
    setSaving(true);
    setError(null);
    try {
      const updated = await riskSettingsApi.update({ ...settings, behavioral_rules: rules });
      setVolAnual(updated.vol_anual);
      setVolDiaria(updated.vol_diaria);
      await Promise.all([
        riskSettingsApi.replaceConvictionTiers(tiers),
        riskSettingsApi.replaceStopLayers(layers),
        riskSettingsApi.replaceDrawdownPhases(phases),
        riskSettingsApi.replaceSeasonalPostures(postures),
      ]);
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-slate-500 text-sm">Carregando...</p>;

  return (
    <div className="space-y-6 pb-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Configurações de risco</h1>
        <button onClick={() => navigate("/risco")} className="text-sm text-green-400">
          Ver status
        </button>
      </div>

      <Section title="Notificações">
        {!isPushSupported() ? (
          <p className="text-sm text-slate-500">
            Este navegador não suporta notificações push (no iPhone, precisa instalar o app na tela inicial primeiro).
          </p>
        ) : (
          <div className="space-y-2">
            <button
              onClick={handleTogglePush}
              disabled={pushBusy}
              className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-sm font-medium py-2.5 rounded-lg"
            >
              {pushEnabled ? "Desativar notificações" : "Ativar notificações"}
            </button>
            {pushEnabled && (
              <button
                onClick={handleTestPush}
                disabled={pushBusy}
                className="w-full text-xs text-green-400 disabled:opacity-50"
              >
                Enviar notificação de teste
              </button>
            )}
            {pushMessage && <p className="text-xs text-slate-400">{pushMessage}</p>}
          </div>
        )}
      </Section>

      <Section title="1. Capital e orçamento de risco anual">
        <Field label="Capital alocado (R$)">
          <input type="number" step="any" {...numField(setSettings, "capital_alocado")} />
        </Field>
        <Field label="Budget anual de PnL (R$)">
          <input type="number" step="any" {...numField(setSettings, "budget_anual_pnl")} />
        </Field>
        <Field label="Sharpe meta">
          <input type="number" step="any" {...numField(setSettings, "sharpe_meta")} />
        </Field>
        <div className="grid grid-cols-2 gap-3 text-sm text-slate-400 bg-slate-950 rounded-lg px-3 py-2">
          <span>Vol anual (calc.): {formatCurrency(volAnual)}</span>
          <span>Vol diária (calc.): {formatCurrency(volDiaria)}</span>
        </div>
      </Section>

      <Section title="Stops (limites flat)">
        <Field label="Stop loss anual / Max DD (R$)">
          <input type="number" step="any" {...numField(setSettings, "stop_loss_anual")} />
        </Field>
        <Field label="Stop loss mensal (R$)">
          <input type="number" step="any" {...numField(setSettings, "stop_loss_mensal")} />
        </Field>
        <Field label="Stop loss diário (R$)">
          <input type="number" step="any" {...numField(setSettings, "stop_loss_diario")} />
        </Field>
      </Section>

      <Section title="Hierarquia de stops — camadas (alerta + stop duro)">
        {layers.map((layer, i) => (
          <div key={layer.level} className="bg-slate-950 rounded-lg p-3 mb-2 space-y-2">
            <p className="text-sm font-medium text-slate-200 capitalize">{layer.level}</p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Alerta amarelo (R$)">
                <input
                  type="number"
                  step="any"
                  value={layer.alerta_amarelo}
                  onChange={(e) =>
                    setLayers((ls) => ls.map((l, idx) => (idx === i ? { ...l, alerta_amarelo: Number(e.target.value) } : l)))
                  }
                />
              </Field>
              <Field label="Stop duro (R$)">
                <input
                  type="number"
                  step="any"
                  value={layer.stop_duro}
                  onChange={(e) =>
                    setLayers((ls) => ls.map((l, idx) => (idx === i ? { ...l, stop_duro: Number(e.target.value) } : l)))
                  }
                />
              </Field>
            </div>
            <Field label="Motivação / notas">
              <textarea
                rows={2}
                value={layer.motivo ?? ""}
                onChange={(e) => setLayers((ls) => ls.map((l, idx) => (idx === i ? { ...l, motivo: e.target.value } : l)))}
              />
            </Field>
          </div>
        ))}
      </Section>

      <Section title="2. Risco por trade (% do stop anual)">
        {tiers.map((tier, i) => (
          <div key={i} className="bg-slate-950 rounded-lg p-3 mb-2 space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Convicção">
                <input
                  value={tier.label}
                  onChange={(e) => setTiers((ts) => ts.map((t, idx) => (idx === i ? { ...t, label: e.target.value } : t)))}
                />
              </Field>
              <Field label="% do stop anual">
                <input
                  type="number"
                  step="any"
                  value={Math.round(tier.pct_of_stop_anual * 1000) / 10}
                  onChange={(e) =>
                    setTiers((ts) =>
                      ts.map((t, idx) => (idx === i ? { ...t, pct_of_stop_anual: Number(e.target.value) / 100 } : t))
                    )
                  }
                />
              </Field>
            </div>
            <Field label="Notas">
              <input
                value={tier.notes ?? ""}
                onChange={(e) => setTiers((ts) => ts.map((t, idx) => (idx === i ? { ...t, notes: e.target.value } : t)))}
              />
            </Field>
            <p className="text-xs text-slate-500">
              Risco máximo: {formatCurrency((settings.stop_loss_anual ?? 0) * tier.pct_of_stop_anual)}
            </p>
            <button
              onClick={() => setTiers((ts) => ts.filter((_, idx) => idx !== i))}
              className="text-xs text-red-400"
            >
              remover
            </button>
          </div>
        ))}
        <button
          onClick={() =>
            setTiers((ts) => [...ts, { label: "nova", pct_of_stop_anual: 0.1, notes: "", order_index: ts.length }])
          }
          className="text-xs text-green-400"
        >
          + adicionar nível de convicção
        </button>
      </Section>

      <Section title="3. Limites de concentração">
        <Field label="Risco máx. por TESE (R$)">
          <input type="number" step="any" {...numField(setSettings, "risco_max_tese")} />
        </Field>
        <Field label="Risco máx. por CLASSE (R$)">
          <input type="number" step="any" {...numField(setSettings, "risco_max_classe")} />
        </Field>
        <Field label="Nº máx. de trades simultâneos">
          <input type="number" step="1" {...numField(setSettings, "max_trades_simultaneos")} />
        </Field>
        <Field label="Nº máx. de teses simultâneas">
          <input type="number" step="1" {...numField(setSettings, "max_teses_simultaneas")} />
        </Field>
      </Section>

      <Section title="4. Regras comportamentais (não negociáveis)">
        {rules.map((rule, i) => (
          <div key={i} className="flex gap-2 mb-2">
            <span className="text-slate-500 text-sm pt-2">{i + 1}.</span>
            <textarea
              rows={2}
              value={rule}
              onChange={(e) => setRules((rs) => rs.map((r, idx) => (idx === i ? e.target.value : r)))}
            />
            <button onClick={() => setRules((rs) => rs.filter((_, idx) => idx !== i))} className="text-red-400 text-xs">
              x
            </button>
          </div>
        ))}
        <button onClick={() => setRules((rs) => [...rs, ""])} className="text-xs text-green-400">
          + adicionar regra
        </button>
      </Section>

      <Section title="Drawdown dinâmico por fase de PnL construído">
        {phases.map((phase, i) => (
          <div key={i} className="bg-slate-950 rounded-lg p-3 mb-2 space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <Field label="PnL mínimo da fase (R$)">
                <input
                  type="number"
                  step="any"
                  value={phase.pnl_min}
                  onChange={(e) => setPhases((ps) => ps.map((p, idx) => (idx === i ? { ...p, pnl_min: Number(e.target.value) } : p)))}
                />
              </Field>
              <Field label="PnL máximo (vazio = sem teto)">
                <input
                  type="number"
                  step="any"
                  value={phase.pnl_max ?? ""}
                  onChange={(e) =>
                    setPhases((ps) =>
                      ps.map((p, idx) => (idx === i ? { ...p, pnl_max: e.target.value === "" ? null : Number(e.target.value) } : p))
                    )
                  }
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Drawdown máx. permitido (%)">
                <input
                  type="number"
                  step="any"
                  value={Math.round(phase.drawdown_max_pct * 1000) / 10}
                  onChange={(e) =>
                    setPhases((ps) =>
                      ps.map((p, idx) => (idx === i ? { ...p, drawdown_max_pct: Number(e.target.value) / 100 } : p))
                    )
                  }
                />
              </Field>
              <Field label="Floor mínimo (R$)">
                <input
                  type="number"
                  step="any"
                  value={phase.floor_minimo}
                  onChange={(e) => setPhases((ps) => ps.map((p, idx) => (idx === i ? { ...p, floor_minimo: Number(e.target.value) } : p)))}
                />
              </Field>
            </div>
            <button onClick={() => setPhases((ps) => ps.filter((_, idx) => idx !== i))} className="text-xs text-red-400">
              remover
            </button>
          </div>
        ))}
        <button
          onClick={() =>
            setPhases((ps) => [
              ...ps,
              { pnl_min: 0, pnl_max: null, drawdown_max_pct: 0.3, floor_minimo: 0, order_index: ps.length },
            ])
          }
          className="text-xs text-green-400"
        >
          + adicionar fase
        </button>
      </Section>

      <Section title="Postura sazonal">
        {postures.map((posture, i) => (
          <div key={i} className="bg-slate-950 rounded-lg p-3 mb-2 space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Período">
                <input
                  value={posture.periodo}
                  onChange={(e) => setPostures((ps) => ps.map((p, idx) => (idx === i ? { ...p, periodo: e.target.value } : p)))}
                />
              </Field>
              <Field label="Situação de PnL">
                <input
                  value={posture.situacao_pnl}
                  onChange={(e) =>
                    setPostures((ps) => ps.map((p, idx) => (idx === i ? { ...p, situacao_pnl: e.target.value } : p)))
                  }
                />
              </Field>
            </div>
            <Field label="Postura">
              <input
                value={posture.postura}
                onChange={(e) => setPostures((ps) => ps.map((p, idx) => (idx === i ? { ...p, postura: e.target.value } : p)))}
              />
            </Field>
            <button onClick={() => setPostures((ps) => ps.filter((_, idx) => idx !== i))} className="text-xs text-red-400">
              remover
            </button>
          </div>
        ))}
        <button
          onClick={() =>
            setPostures((ps) => [...ps, { periodo: "", situacao_pnl: "", postura: "", order_index: ps.length }])
          }
          className="text-xs text-green-400"
        >
          + adicionar postura
        </button>
      </Section>

      {error && <p className="text-red-400 text-sm">{error}</p>}
      {savedAt && !error && <p className="text-green-400 text-sm">Salvo.</p>}

      <button
        onClick={handleSaveAll}
        disabled={saving}
        className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-3 rounded-lg sticky bottom-20"
      >
        {saving ? "Salvando..." : "Salvar alterações"}
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-300 mb-2 bg-slate-800/60 px-3 py-1.5 rounded">{title}</h2>
      <div className="space-y-3 px-1">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label>{label}</label>
      {children}
    </div>
  );
}
