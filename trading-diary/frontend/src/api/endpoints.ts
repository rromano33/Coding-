import { api, setToken } from "./client";
import type {
  BreakdownItem,
  ConvictionTier,
  ConvictionTierInput,
  DailyNote,
  DailyNoteInput,
  DailyNotePrefill,
  DrawdownPhase,
  DrawdownPhaseInput,
  EquityCurvePoint,
  PerformanceSummary,
  RiskSettings,
  RiskSettingsInput,
  RiskStatus,
  SeasonalPosture,
  SeasonalPostureInput,
  StopLayer,
  StopLayerInput,
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
  updatePrice: (id: number, currentPrice: number) => api.patch<Trade>(`/trades/${id}/price`, { current_price: currentPrice }),
  remove: (id: number) => api.delete<void>(`/trades/${id}`),
};

export const dailyNotesApi = {
  list: () => api.get<DailyNote[]>("/daily-notes"),
  get: (id: number) => api.get<DailyNote>(`/daily-notes/${id}`),
  prefill: (date: string) => api.get<DailyNotePrefill>(`/daily-notes/prefill?date=${date}`),
  create: (payload: DailyNoteInput) => api.post<DailyNote>("/daily-notes", payload),
  update: (id: number, payload: Partial<DailyNoteInput>) => api.put<DailyNote>(`/daily-notes/${id}`, payload),
  remove: (id: number) => api.delete<void>(`/daily-notes/${id}`),
};

export const statsApi = {
  summary: () => api.get<PerformanceSummary>("/stats/summary"),
  equityCurve: () => api.get<EquityCurvePoint[]>("/stats/equity-curve"),
  byStrategy: () => api.get<BreakdownItem[]>("/stats/by-strategy"),
  byAsset: () => api.get<BreakdownItem[]>("/stats/by-asset"),
  byMarket: () => api.get<BreakdownItem[]>("/stats/by-market"),
};

export const riskSettingsApi = {
  get: () => api.get<RiskSettings>("/risk-settings"),
  update: (payload: RiskSettingsInput) => api.put<RiskSettings>("/risk-settings", payload),
  listConvictionTiers: () => api.get<ConvictionTier[]>("/risk-settings/conviction-tiers"),
  replaceConvictionTiers: (items: ConvictionTierInput[]) =>
    api.put<ConvictionTier[]>("/risk-settings/conviction-tiers", items),
  listStopLayers: () => api.get<StopLayer[]>("/risk-settings/stop-layers"),
  replaceStopLayers: (items: StopLayerInput[]) => api.put<StopLayer[]>("/risk-settings/stop-layers", items),
  listDrawdownPhases: () => api.get<DrawdownPhase[]>("/risk-settings/drawdown-phases"),
  replaceDrawdownPhases: (items: DrawdownPhaseInput[]) =>
    api.put<DrawdownPhase[]>("/risk-settings/drawdown-phases", items),
  listSeasonalPostures: () => api.get<SeasonalPosture[]>("/risk-settings/seasonal-postures"),
  replaceSeasonalPostures: (items: SeasonalPostureInput[]) =>
    api.put<SeasonalPosture[]>("/risk-settings/seasonal-postures", items),
};

export const riskApi = {
  status: () => api.get<RiskStatus>("/risk/status"),
};

export const pushApi = {
  publicKey: () => api.get<{ public_key: string }>("/push/public-key"),
  subscribe: (subscription: PushSubscriptionJSON) => api.post<void>("/push/subscribe", subscription),
  unsubscribe: (endpoint: string) => api.post<void>("/push/unsubscribe", { endpoint }),
  test: () => api.post<void>("/push/test", {}),
};
