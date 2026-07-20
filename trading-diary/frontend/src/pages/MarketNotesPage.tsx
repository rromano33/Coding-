import { useEffect, useState } from "react";
import { marketNotesApi } from "../api/endpoints";
import type { MarketNote, MarketNoteInput } from "../types";
import { formatDate } from "../utils/format";

const EMPTY: MarketNoteInput = {
  date: new Date().toISOString(),
  title: "",
  content: "",
  tags: "",
};

export default function MarketNotesPage() {
  const [notes, setNotes] = useState<MarketNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<MarketNoteInput>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  function refresh() {
    marketNotesApi.list().then((data) => {
      setNotes(data);
      setLoading(false);
    });
  }

  useEffect(refresh, []);

  function startEdit(note: MarketNote) {
    setEditingId(note.id);
    setForm({ date: note.date, title: note.title, content: note.content, tags: note.tags ?? "" });
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
        await marketNotesApi.update(editingId, payload);
      } else {
        await marketNotesApi.create(payload);
      }
      setShowForm(false);
      refresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir esta nota de mercado?")) return;
    await marketNotesApi.remove(id);
    refresh();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Movimentos de mercado</h1>
        <button
          onClick={startNew}
          className="bg-green-600 hover:bg-green-500 text-white text-sm font-medium px-3 py-2 rounded-lg"
        >
          + Nota
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
            <label>Título</label>
            <input required value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          </div>
          <div>
            <label>Conteúdo</label>
            <textarea
              rows={4}
              required
              value={form.content}
              onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
            />
          </div>
          <div>
            <label>Tags</label>
            <input value={form.tags ?? ""} onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))} />
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
        <p className="text-slate-500 text-sm text-center py-12">Nenhuma nota de mercado ainda.</p>
      )}

      <div className="space-y-2">
        {notes.map((note) => (
          <div key={note.id} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium text-slate-100">{note.title}</p>
                <p className="text-xs text-slate-500">
                  {formatDate(note.date)} {note.tags && `· ${note.tags}`}
                </p>
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
            <p className="text-sm text-slate-400 mt-2 whitespace-pre-wrap">{note.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
