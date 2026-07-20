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


class TradeRead(TradeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pnl: float | None = None
    r_multiple: float | None = None
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
