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
    currency: str | None = None  # ex: BRL, USD, JPY; vazio = BRL
    fx_rate_to_brl: float | None = None
    contract_multiplier: float = 1.0
    risk_class: str | None = None  # rates | fx | equities | other
    manual_adjustment: float = 0.0  # ajuste manual em R$ (scaling intraday)


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
    currency: str | None = None
    fx_rate_to_brl: float | None = None
    contract_multiplier: float | None = None
    risk_class: str | None = None
    manual_adjustment: float | None = None


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


# ---- Daily note (diário macro) ----

class DailyNoteBase(BaseModel):
    date: datetime.datetime
    ontem: str | None = None
    comentario_geral: str | None = None
    oil_commodities: str | None = None
    bolsas: str | None = None
    juros_dm: str | None = None
    pricing_dm: str | None = None
    dxy_dmfx: str | None = None
    moedas_em: str | None = None
    brl_comment: str | None = None
    rates_em: str | None = None
    pricing_em: str | None = None
    meu_book: str | None = None
    pnl_por_classe: str | None = None
    pnl_rates: float | None = None
    pnl_fx: float | None = None
    pnl_equities: float | None = None
    pnl_other: float | None = None
    posicoes: str | None = None
    espero_amanha: str | None = None
    vol_total_usd: float | None = None
    vol_total_brl: float | None = None
    risco_portfolio: str | None = None


class DailyNoteCreate(DailyNoteBase):
    pass


class DailyNoteUpdate(BaseModel):
    date: datetime.datetime | None = None
    ontem: str | None = None
    comentario_geral: str | None = None
    oil_commodities: str | None = None
    bolsas: str | None = None
    juros_dm: str | None = None
    pricing_dm: str | None = None
    dxy_dmfx: str | None = None
    moedas_em: str | None = None
    brl_comment: str | None = None
    rates_em: str | None = None
    pricing_em: str | None = None
    meu_book: str | None = None
    pnl_por_classe: str | None = None
    pnl_rates: float | None = None
    pnl_fx: float | None = None
    pnl_equities: float | None = None
    pnl_other: float | None = None
    posicoes: str | None = None
    espero_amanha: str | None = None
    vol_total_usd: float | None = None
    vol_total_brl: float | None = None
    risco_portfolio: str | None = None


class DailyNoteRead(DailyNoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DailyNotePrefill(BaseModel):
    ontem: str | None = None
    posicoes: str | None = None


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

    postura_atual: str | None

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
