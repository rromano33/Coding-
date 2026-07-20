import { api, setToken } from "./client";
import type {
  BreakdownItem,
  EquityCurvePoint,
  JournalEntry,
  JournalEntryInput,
  MarketNote,
  MarketNoteInput,
  PerformanceSummary,
  Trade,
  TradeInput,
  User,
} from "../types";

export const authApi = {
  async register(email: string, password: string, displayName?: string): Promise<User> {
    return api.post<User>("/auth/register", { email, password, display_name: displayName || null });
  },
  async login(email: string, password: string): Promise<User> {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const token = await api.postForm<{ access_token: string }>("/auth/login", form);
    setToken(token.access_token);
    return api.get<User>("/auth/me");
  },
  me: () => api.get<User>("/auth/me"),
};

export const tradesApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    return api.get<Trade[]>(`/trades${qs}`);
  },
  get: (id: number) => api.get<Trade>(`/trades/${id}`),
  create: (payload: TradeInput) => api.post<Trade>("/trades", payload),
  update: (id: number, payload: Partial<TradeInput>) => api.put<Trade>(`/trades/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/trades/${id}`),
};

export const marketNotesApi = {
  list: () => api.get<MarketNote[]>("/market-notes"),
  create: (payload: MarketNoteInput) => api.post<MarketNote>("/market-notes", payload),
  update: (id: number, payload: Partial<MarketNoteInput>) => api.put<MarketNote>(`/market-notes/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/market-notes/${id}`),
};

export const journalApi = {
  list: () => api.get<JournalEntry[]>("/journal"),
  create: (payload: JournalEntryInput) => api.post<JournalEntry>("/journal", payload),
  update: (id: number, payload: Partial<JournalEntryInput>) => api.put<JournalEntry>(`/journal/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/journal/${id}`),
};

export const statsApi = {
  summary: () => api.get<PerformanceSummary>("/stats/summary"),
  equityCurve: () => api.get<EquityCurvePoint[]>("/stats/equity-curve"),
  byStrategy: () => api.get<BreakdownItem[]>("/stats/by-strategy"),
  byAsset: () => api.get<BreakdownItem[]>("/stats/by-asset"),
  byMarket: () => api.get<BreakdownItem[]>("/stats/by-market"),
};
