import { useEffect, useState } from "react";
import { dailyNotesApi } from "../api/endpoints";
import type { DailyNote, DailyNoteInput } from "../types";
import { formatDate } from "../utils/format";

const EMPTY: DailyNoteInput = {
  date: new Date().toISOString(),
  ontem: "",
  comentario_geral: "",
  oil_commodities: "",
  bolsas: "",
  juros_dm: "",
  pricing_dm: "",
  dxy_dmfx: "",
  moedas_em: "",
  brl_comment: "",
  rates_em: "",
  pricing_em: "",
  meu_book: "",
  pnl_por_classe: "",
  posicoes: "",
  espero_amanha: "",
  vol_total_usd: null,
  vol_total_brl: null,
  risco_portfolio: "",
};

const SECTIONS: { key: keyof DailyNoteInput; label: string; rows?: number }[] = [
  { key: "ontem", label: "Ontem", rows: 2 },
  { key: "comentario_geral", label: "Comentário geral", rows: 3 },
  { key: "oil_commodities", label: "Oil/Commodities", rows: 2 },
  { key: "bolsas", label: "Bolsas", rows: 2 },
  { key: "juros_dm", label: "Juros DM", rows: 2 },
  { key: "pricing_dm", label: "Pricing DM", rows: 2 },
  { key: "dxy_dmfx", label: "DXY e DMFX", rows: 2 },
  { key: "moedas_em", label: "Moedas EM", rows: 2 },
  { key: "brl_comment", label: "BRL", rows: 2 },
  { key: "rates_em", label: "Rates EM", rows: 2 },
  { key: "pricing_em", label: "Pricing EM", rows: 2 },
  { key: "meu_book", label: "Meu book (resultado e comentário)", rows: 3 },
  { key: "pnl_por_classe", label: "P&L por classe", rows: 2 },
  { key: "posicoes", label: "Posições", rows: 3 },
  { key: "espero_amanha", label: "O que espero de amanhã", rows: 2 },
  { key: "risco_portfolio", label: "Risco de portfólio (opcional)", rows: 2 },
];

export default function DailyNotePage() {
  const [notes, setNotes] = useState<DailyNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<DailyNoteInput>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [prefilling, setPrefilling] = useState(false);

  function refresh() {
    dailyNotesApi.list().then((data) => {
      setNotes(data);
      setLoading(false);
    });
  }

  useEffect(refresh, []);

  function startEdit(note: DailyNote) {
    setEditingId(note.id);
    setForm({ ...note });
    setShowForm(true);
  }

  async function startNewToday() {
    setPrefilling(true);
    const today = new Date().toISOString();
    try {
      const prefill = await dailyNotesApi.prefill(today.slice(0, 10));
      setEditingId(null);
      setForm({
        ...EMPTY,
        date: today,
        ontem: prefill.ontem ?? "",
        pnl_por_classe: prefill.pnl_por_classe ?? "",
        posicoes: prefill.posicoes ?? "",
      });
      setShowForm(true);
    } finally {
      setPrefilling(false);
    }
  }

  function startNewBlank() {
    setEditingId(null);
    setForm({ ...EMPTY, date: new Date().toISOString() });
    setShowForm(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, date: new Date(form.date).toISOString() };
      if (editingId) {
        await dailyNotesApi.update(editingId, payload);
      } else {
        await dailyNotesApi.create(payload);
      }
      setShowForm(false);
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este registro do diário?")) return;
    await dailyNotesApi.remove(id);
    refresh();
  }

  function field(key: keyof DailyNoteInput) {
    return {
      value: (form[key] ?? "") as string,
      onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => setForm((f) => ({ ...f, [key]: e.target.value })),
    };
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Diário</h1>
        <div className="flex gap-2">
          <button
            onClick={startNewToday}
            disabled={prefilling}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium px-3 py-2 rounded-lg"
          >
            {prefilling ? "..." : "+ Hoje"}
          </button>
          <button
            onClick={startNewBlank}
            className="border border-slate-800 text-slate-400 text-sm font-medium px-3 py-2 rounded-lg"
          >
            + Em branco
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-4 space-y-3">
          <div>
            <label>Data</label>
            <input
              type="date"
              required
              value={form.date.slice(0, 10)}
              onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
            />
          </div>

          {SECTIONS.map((s) => (
            <div key={s.key}>
              <label>{s.label}</label>
              <textarea rows={s.rows ?? 2} {...field(s.key)} />
            </div>
          ))}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label>Vol total estimada (USD)</label>
              <input
                type="number"
                step="any"
                value={form.vol_total_usd ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, vol_total_usd: e.target.value === "" ? null : Number(e.target.value) }))}
              />
            </div>
            <div>
              <label>Vol total estimada (BRL)</label>
              <input
                type="number"
                step="any"
                value={form.vol_total_brl ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, vol_total_brl: e.target.value === "" ? null : Number(e.target.value) }))}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2 rounded-lg"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-4 text-slate-400 text-sm">
              Cancelar
            </button>
          </div>
        </form>
      )}

      {loading && <p className="text-slate-500 text-sm">Carregando...</p>}
      {!loading && notes.length === 0 && !showForm && (
        <p className="text-slate-500 text-sm text-center py-12">Nenhum registro ainda.</p>
      )}

      <div className="space-y-2">
        {notes.map((note) => (
          <div key={note.id} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium text-slate-100">{formatDate(note.date)}</p>
                {note.comentario_geral && (
                  <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{note.comentario_geral}</p>
                )}
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                <button onClick={() => startEdit(note)} className="text-green-400">
                  editar
                </button>
                <button onClick={() => handleDelete(note.id)} className="text-red-400">
                  excluir
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
