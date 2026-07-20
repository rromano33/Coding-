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
  pnl: number | null;
  r_multiple: number | null;
  created_at: string;
  updated_at: string;
}

export type TradeInput = Omit<Trade, "id" | "pnl" | "r_multiple" | "created_at" | "updated_at">;

export interface MarketNote {
  id: number;
  date: string;
  title: string;
  content: string;
  tags: string | null;
  created_at: string;
  updated_at: string;
}

export type MarketNoteInput = Omit<MarketNote, "id" | "created_at" | "updated_at">;

export interface JournalEntry {
  id: number;
  date: string;
  mood: string | null;
  discipline_score: number | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export type JournalEntryInput = Omit<JournalEntry, "id" | "created_at" | "updated_at">;

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
