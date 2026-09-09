import { useEffect, useMemo, useState } from "react";
import { journalApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { MOODS, moodEmoji, type JournalEntry } from "../types";
import { formatDateTime } from "../utils/format";

function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Erro de conexão. Tenta de novo.";
}

function monthYearKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthYearLabel(iso: string): string {
  const label = new Date(iso).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function isSameDay(iso: string, dateStr: string): boolean {
  // dateStr vem de <input type="date">, formato YYYY-MM-DD, comparado em horário local
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return local === dateStr;
}

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [mood, setMood] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [dateFilter, setDateFilter] = useState("");

  function refresh() {
    setLoading(true);
    setLoadError(null);
    journalApi
      .list()
      .then((data) => setEntries(data))
      .catch((err) => setLoadError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  function startEdit(entry: JournalEntry) {
    setEditingId(entry.id);
    setText(entry.text);
    setMood(entry.mood);
    setSaveError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setText("");
    setMood(null);
    setSaveError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || mood === null) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editingId) {
        await journalApi.update(editingId, { text, mood });
      } else {
        await journalApi.create({ text, mood });
      }
      cancelEdit();
      refresh();
    } catch (err) {
      setSaveError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Excluir esta entrada?")) return;
    try {
      await journalApi.remove(id);
      refresh();
    } catch (err) {
      setLoadError(errorMessage(err));
    }
  }

  const filtered = useMemo(
    () => (dateFilter ? entries.filter((e) => isSameDay(e.created_at, dateFilter)) : entries),
    [entries, dateFilter]
  );

  const groups = useMemo(() => {
    const map = new Map<string, { label: string; items: JournalEntry[] }>();
    for (const entry of filtered) {
      const key = monthYearKey(entry.created_at);
      if (!map.has(key)) map.set(key, { label: monthYearLabel(entry.created_at), items: [] });
      map.get(key)!.items.push(entry);
    }
    return Array.from(map.values());
  }, [filtered]);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Diário</h1>

      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-4 space-y-3">
        <textarea
          rows={4}
          placeholder="O que você está pensando?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-slate-100 placeholder:text-slate-500"
        />
        <div className="flex items-center justify-between gap-2">
          {MOODS.map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => setMood(m.value)}
              title={m.label}
              aria-label={m.label}
              className={`text-2xl leading-none rounded-full p-2 transition ${
                mood === m.value ? "bg-green-600/30 ring-2 ring-green-500" : "hover:bg-slate-800"
              }`}
            >
              {m.emoji}
            </button>
          ))}
        </div>
        {saveError && <p className="text-red-400 text-sm">{saveError}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving || !text.trim() || mood === null}
            className="flex-1 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium py-2 rounded-lg"
          >
            {saving ? "Salvando..." : editingId ? "Salvar edição" : "Salvar"}
          </button>
          {editingId && (
            <button type="button" onClick={cancelEdit} className="px-4 text-slate-400 text-sm">
              Cancelar
            </button>
          )}
        </div>
      </form>

      <div className="flex items-center gap-2 mb-4">
        <label className="text-sm text-slate-400 shrink-0">Buscar por data</label>
        <input
          type="date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-sm text-slate-100"
        />
        {dateFilter && (
          <button onClick={() => setDateFilter("")} className="text-xs text-green-400 shrink-0">
            limpar
          </button>
        )}
      </div>

      {loading && <p className="text-slate-500 text-sm">Carregando...</p>}

      {!loading && loadError && (
        <div className="bg-red-950/40 border border-red-900 rounded-xl px-4 py-3 text-sm text-red-300 flex items-center justify-between gap-2">
          <span>{loadError}</span>
          <button onClick={refresh} className="text-red-200 underline shrink-0">
            tentar de novo
          </button>
        </div>
      )}

      {!loading && !loadError && entries.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-12">Nenhuma entrada ainda.</p>
      )}

      {!loading && !loadError && entries.length > 0 && filtered.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-12">Nenhuma entrada nesse dia.</p>
      )}

      {!loading &&
        !loadError &&
        groups.map((group) => (
          <div key={group.label} className="mb-5">
            <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{group.label}</h2>
            <div className="space-y-2">
              {group.items.map((entry) => (
                <div key={entry.id} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2 min-w-0">
                      <span className="text-xl leading-none shrink-0">{moodEmoji(entry.mood)}</span>
                      <div className="min-w-0">
                        <p className="text-xs text-slate-500">{formatDateTime(entry.created_at)}</p>
                        <p className="text-slate-100 whitespace-pre-wrap break-words">{entry.text}</p>
                      </div>
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
                </div>
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}
