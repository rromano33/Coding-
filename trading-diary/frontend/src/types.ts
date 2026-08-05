export type Direction = "long" | "short";
export type TradeStatus = "open" | "closed";

export const MARKETS = [
  { value: "acoes", label: "Ações" },
  { value: "futuros", label: "Futuros" },
  { value: "fx", label: "FX" },
  { value: "opcoes", label: "Opções" },
  { value: "cripto", label: "Cripto" },
  { value: "renda_fixa", label: "Renda fixa" },
  { value: "outro", label: "Outro" },
] as const;

export type RiskClass = "rates" | "fx" | "equities" | "other";

export const RISK_CLASSES: { value: RiskClass; label: string }[] = [
  { value: "rates", label: "RATES" },
  { value: "fx", label: "FX" },
  { value: "equities", label: "EQUITIES" },
  { value: "other", label: "OTHER" },
];

export const DEFAULT_RISK_CLASS_BY_MARKET: Record<string, RiskClass> = {
  acoes: "equities",
  futuros: "rates",
  fx: "fx",
  opcoes: "other",
  cripto: "equities",
  renda_fixa: "rates",
  outro: "other",
};

export interface Trade {
  id: number;
  asset: string;
  market: string;
  direction: Direction;
  status: TradeStatus;
  entry_date: string;
  entry_price: number;
  exit_date: string | null;
  exit_price: number | null;
  quantity: number;
  stop_price: number | null;
  target_price: number | null;
  fees: number;
  strategy: string | null;
  tags: string | null;
  thesis: string | null;
  notes: string | null;
  emotions: string | null;
  conviction: Conviction | null;
  vol_diaria_pct: number | null;
  currency: string | null;
  fx_rate_to_brl: number | null;
  contract_multiplier: number;
  risk_class: RiskClass | null;
  manual_adjustment: number;
  pnl: number | null;
  r_multiple: number | null;
  current_price: number | null;
  current_price_updated_at: string | null;
  unrealized_pnl: number | null;
  stop_alert: "perto" | "atingido" | null;
  created_at: string;
  updated_at: string;
}

export type Conviction = "baixa" | "media" | "alta" | "extrema";

export const CONVICTIONS: { value: Conviction; label: string }[] = [
  { value: "baixa", label: "Baixa (exploratório)" },
  { value: "media", label: "Média (padrão)" },
  { value: "alta", label: "Alta (convicção)" },
  { value: "extrema", label: "Extrema (raro)" },
];

export type TradeInput = Omit<
  Trade,
  | "id"
  | "pnl"
  | "r_multiple"
  | "created_at"
  | "updated_at"
  | "current_price"
  | "current_price_updated_at"
  | "unrealized_pnl"
  | "stop_alert"
>;

export interface DailyNote {
  id: number;
  date: string;
  ontem: string | null;
  comentario_geral: string | null;
  oil_commodities: string | null;
  bolsas: string | null;
  juros_dm: string | null;
  pricing_dm: string | null;
  dxy_dmfx: string | null;
  moedas_em: string | null;
  brl_comment: string | null;
  rates_em: string | null;
  pricing_em: string | null;
  meu_book: string | null;
  pnl_por_classe: string | null;
  pnl_rates: number | null;
  pnl_fx: number | null;
  pnl_equities: number | null;
  pnl_other: number | null;
  posicoes: string | null;
  espero_amanha: string | null;
  vol_total_usd: number | null;
  vol_total_brl: number | null;
  risco_portfolio: string | null;
  created_at: string;
  updated_at: string;
}

export type DailyNoteInput = Omit<DailyNote, "id" | "created_at" | "updated_at">;

export interface DailyNotePrefill {
  ontem: string | null;
  posicoes: string | null;
}

export interface PerformanceSummary {
  total_trades: number;
  closed_trades: number;
  open_trades: number;
  total_pnl: number;
  win_rate: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  avg_r_multiple: number | null;
  best_trade_pnl: number | null;
  worst_trade_pnl: number | null;
  max_drawdown: number | null;
}

export interface EquityCurvePoint {
  date: string;
  cumulative_pnl: number;
  trade_count: number;
}

export interface BreakdownItem {
  key: string;
  trade_count: number;
  total_pnl: number;
  win_rate: number | null;
}

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  created_at: string;
}

// ---- Risk settings ----

export interface RiskSettings {
  capital_alocado: number;
  budget_anual_pnl: number;
  sharpe_meta: number;
  stop_loss_anual: number;
  stop_loss_mensal: number;
  stop_loss_diario: number;
  risco_max_tese: number;
  risco_max_classe: number;
  max_trades_simultaneos: number;
  max_teses_simultaneas: number;
  behavioral_rules: string[];
  vol_anual: number;
  vol_diaria: number;
  updated_at: string;
}

export type RiskSettingsInput = Partial<Omit<RiskSettings, "vol_anual" | "vol_diaria" | "updated_at">>;

export interface ConvictionTier {
  id: number;
  label: string;
  pct_of_stop_anual: number;
  notes: string | null;
  order_index: number;
  risco_maximo: number;
}

export type ConvictionTierInput = Omit<ConvictionTier, "id" | "risco_maximo">;

export interface StopLayer {
  id: number;
  level: string;
  alerta_amarelo: number;
  stop_duro: number;
  motivo: string | null;
  order_index: number;
}

export type StopLayerInput = Omit<StopLayer, "id">;

export interface DrawdownPhase {
  id: number;
  pnl_min: number;
  pnl_max: number | null;
  drawdown_max_pct: number;
  floor_minimo: number;
  order_index: number;
}

export type DrawdownPhaseInput = Omit<DrawdownPhase, "id">;

export interface SeasonalPosture {
  id: number;
  periodo: string;
  situacao_pnl: string;
  postura: string;
  order_index: number;
}

export type SeasonalPostureInput = Omit<SeasonalPosture, "id">;

export interface RiskAlert {
  severity: "alerta" | "stop";
  message: string;
  trade_id: number | null;
}

export interface ConcentrationItem {
  key: string;
  risco_atual: number;
  limite: number;
  over: boolean;
}

export interface RiskStatus {
  pnl_today: number;
  pnl_month: number;
  pnl_year: number;
  budget_anual_pnl: number;
  pct_of_budget_year: number | null;
  drawdown_atual: number;
  drawdown_permitido: number | null;
  drawdown_floor_minimo: number | null;
  drawdown_phase_label: string | null;
  trades_abertos: number;
  max_trades_simultaneos: number;
  teses_abertas: number;
  max_teses_simultaneas: number;
  concentracao_tese: ConcentrationItem[];
  concentracao_classe: ConcentrationItem[];
  postura_atual: string | null;
  alerts: RiskAlert[];
}
