import { useEffect, useState } from "react";
import { journalApi } from "../api/endpoints";
import type { JournalEntry, JournalEntryInput } from "../types";
import { formatDate } from "../utils/format";

const MOODS = ["confiante", "ansioso", "disciplinado", "impulsivo", "frustrado", "neutro"];

const EMPTY: JournalEntryInput = {
  date: new Date().toISOString(),
  mood: "neutro",
  discipline_score: 3,
  content: "",
};

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<JournalEntryInput>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  function refresh() {
    journalApi.list().then((data) => {
      setEntries(data);
      setLoading(false);
    });
  }

  useEffect(refresh, []);

  function startEdit(entry: JournalEntry) {
    setEditingId(entry.id);
    setForm({
      date: entry.date,
      mood: entry.mood ?? "neutro",
      discipline_score: entry.discipline_score ?? 3,
      content: entry.content,
    });
    setShowForm(true);
  }

  function startNew() {
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
        await journalApi.update(editingId, payload);
      } else {
        await journalApi.create(payload);
      }
      setShowForm(false);
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir este registro do diário?")) return;
    await journalApi.remove(id);
    refresh();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Impressões & disciplina</h1>
        <button
          onClick={startNew}
          className="bg-green-600 hover:bg-green-500 text-white text-sm font-medium px-3 py-2 rounded-lg"
        >
          + Registro
        </button>
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
          <div>
            <label>Estado emocional</label>
            <select value={form.mood ?? "neutro"} onChange={(e) => setForm((f) => ({ ...f, mood: e.target.value }))}>
              {MOODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Nota de disciplina (1-5)</label>
            <input
              type="number"
              min={1}
              max={5}
              value={form.discipline_score ?? 3}
              onChange={(e) => setForm((f) => ({ ...f, discipline_score: Number(e.target.value) }))}
            />
          </div>
          <div>
            <label>Impressões do dia</label>
            <textarea
              rows={4}
              required
              value={form.content}
              onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
            />
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
      {!loading && entries.length === 0 && !showForm && (
        <p className="text-slate-500 text-sm text-center py-12">Nenhum registro ainda.</p>
      )}

      <div className="space-y-2">
        {entries.map((entry) => (
          <div key={entry.id} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium text-slate-100 capitalize">{entry.mood || "—"}</p>
                <p className="text-xs text-slate-500">
                  {formatDate(entry.date)}
                  {entry.discipline_score !== null && ` · disciplina ${entry.discipline_score}/5`}
                </p>
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                <button onClick={() => startEdit(entry)} className="text-green-400">
                  editar
                </button>
                <button onClick={() => handleDelete(entry.id)} className="text-red-400">
                  excluir
                </button>
              </div>
            </div>
            <p className="text-sm text-slate-400 mt-2 whitespace-pre-wrap">{entry.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
