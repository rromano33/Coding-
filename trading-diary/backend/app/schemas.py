import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


# ---- Auth ----

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str | None = None
    created_at: datetime.datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Trade ----

class TradeBase(BaseModel):
    asset: str
    market: str = "outro"
    direction: str  # long | short
    status: str = "open"
    entry_date: datetime.datetime
    entry_price: float
    exit_date: datetime.datetime | None = None
    exit_price: float | None = None
    quantity: float
    stop_price: float | None = None
    target_price: float | None = None
    fees: float = 0.0
    strategy: str | None = None
    tags: str | None = None
    thesis: str | None = None
    notes: str | None = None
    emotions: str | None = None
    conviction: str | None = None  # baixa | media | alta | extrema
    vol_diaria_pct: float | None = None  # vol diária estimada do ativo, ex: 0.02 = 2%


class TradeCreate(TradeBase):
    pass


class TradeUpdate(BaseModel):
    asset: str | None = None
    market: str | None = None
    direction: str | None = None
    status: str | None = None
    entry_date: datetime.datetime | None = None
    entry_price: float | None = None
    exit_date: datetime.datetime | None = None
    exit_price: float | None = None
    quantity: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    fees: float | None = None
    strategy: str | None = None
    tags: str | None = None
    thesis: str | None = None
    notes: str | None = None
    emotions: str | None = None
    conviction: str | None = None
    vol_diaria_pct: float | None = None


class TradePriceUpdate(BaseModel):
    current_price: float


class TradeRead(TradeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pnl: float | None = None
    r_multiple: float | None = None
    current_price: float | None = None
    current_price_updated_at: datetime.datetime | None = None
    unrealized_pnl: float | None = None
    stop_alert: str | None = None  # "perto" | "atingido"
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---- Market note ----

class MarketNoteBase(BaseModel):
    date: datetime.datetime
    title: str
    content: str
    tags: str | None = None


class MarketNoteCreate(MarketNoteBase):
    pass


class MarketNoteUpdate(BaseModel):
    date: datetime.datetime | None = None
    title: str | None = None
    content: str | None = None
    tags: str | None = None


class MarketNoteRead(MarketNoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---- Journal entry ----

class JournalEntryBase(BaseModel):
    date: datetime.datetime
    mood: str | None = None
    discipline_score: int | None = None
    content: str


class JournalEntryCreate(JournalEntryBase):
    pass


class JournalEntryUpdate(BaseModel):
    date: datetime.datetime | None = None
    mood: str | None = None
    discipline_score: int | None = None
    content: str | None = None


class JournalEntryRead(JournalEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---- Stats ----

class PerformanceSummary(BaseModel):
    total_trades: int
    closed_trades: int
    open_trades: int
    total_pnl: float
    win_rate: float | None
    avg_win: float | None
    avg_loss: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_r_multiple: float | None
    best_trade_pnl: float | None
    worst_trade_pnl: float | None
    max_drawdown: float | None


class EquityCurvePoint(BaseModel):
    date: datetime.date
    cumulative_pnl: float
    trade_count: int


class BreakdownItem(BaseModel):
    key: str
    trade_count: int
    total_pnl: float
    win_rate: float | None


# ---- Risk settings ----

class RiskSettingsBase(BaseModel):
    capital_alocado: float
    budget_anual_pnl: float
    sharpe_meta: float
    stop_loss_anual: float
    stop_loss_mensal: float
    stop_loss_diario: float
    risco_max_tese: float
    risco_max_classe: float
    max_trades_simultaneos: int
    max_teses_simultaneas: int
    behavioral_rules: list[str] = []


class RiskSettingsUpdate(BaseModel):
    capital_alocado: float | None = None
    budget_anual_pnl: float | None = None
    sharpe_meta: float | None = None
    stop_loss_anual: float | None = None
    stop_loss_mensal: float | None = None
    stop_loss_diario: float | None = None
    risco_max_tese: float | None = None
    risco_max_classe: float | None = None
    max_trades_simultaneos: int | None = None
    max_teses_simultaneas: int | None = None
    behavioral_rules: list[str] | None = None


class RiskSettingsRead(RiskSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    vol_anual: float
    vol_diaria: float
    updated_at: datetime.datetime


class ConvictionTierItem(BaseModel):
    label: str
    pct_of_stop_anual: float
    notes: str | None = None
    order_index: int = 0


class ConvictionTierRead(ConvictionTierItem):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risco_maximo: float


class StopLayerItem(BaseModel):
    level: str
    alerta_amarelo: float
    stop_duro: float
    motivo: str | None = None
    order_index: int = 0


class StopLayerRead(StopLayerItem):
    model_config = ConfigDict(from_attributes=True)

    id: int


class DrawdownPhaseItem(BaseModel):
    pnl_min: float
    pnl_max: float | None = None
    drawdown_max_pct: float
    floor_minimo: float
    order_index: int = 0


class DrawdownPhaseRead(DrawdownPhaseItem):
    model_config = ConfigDict(from_attributes=True)

    id: int


class SeasonalPostureItem(BaseModel):
    periodo: str
    situacao_pnl: str
    postura: str
    order_index: int = 0


class SeasonalPostureRead(SeasonalPostureItem):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---- Risk status (calculado) ----

class RiskAlert(BaseModel):
    severity: str  # "alerta" | "stop"
    message: str
    trade_id: int | None = None


class ConcentrationItem(BaseModel):
    key: str
    risco_atual: float
    limite: float
    over: bool


class RiskStatus(BaseModel):
    pnl_today: float
    pnl_month: float
    pnl_year: float
    budget_anual_pnl: float
    pct_of_budget_year: float | None

    drawdown_atual: float
    drawdown_permitido: float | None
    drawdown_floor_minimo: float | None
    drawdown_phase_label: str | None

    trades_abertos: int
    max_trades_simultaneos: int
    teses_abertas: int
    max_teses_simultaneas: int

    concentracao_tese: list[ConcentrationItem]
    concentracao_classe: list[ConcentrationItem]

    alerts: list[RiskAlert]


# ---- Push notifications ----

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushSubscriptionRemove(BaseModel):
    endpoint: str


class VapidPublicKey(BaseModel):
    public_key: str
