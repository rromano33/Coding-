import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    trades: Mapped[list["Trade"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    market_notes: Mapped[list["MarketNote"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    risk_settings: Mapped["RiskSettings | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    conviction_tiers: Mapped[list["ConvictionTier"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    stop_layers: Mapped[list["StopLayer"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    drawdown_phases: Mapped[list["DrawdownPhase"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    seasonal_postures: Mapped[list["SeasonalPosture"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    asset: Mapped[str] = mapped_column(String(64))
    market: Mapped[str] = mapped_column(String(32), default="outro")  # acoes, futuros, fx, opcoes, cripto, renda_fixa, outro
    direction: Mapped[str] = mapped_column(String(8))  # long | short
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | closed

    entry_date: Mapped[datetime.datetime] = mapped_column(DateTime)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    quantity: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0.0)

    strategy: Mapped[str | None] = mapped_column(String(128), nullable=True)  # também usado como "tese" p/ concentração
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated
    conviction: Mapped[str | None] = mapped_column(String(16), nullable=True)  # baixa | media | alta | extrema
    vol_diaria_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # vol diária estimada do ativo, ex: 0.02 = 2%

    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # última marcação manual (posição aberta)
    current_price_updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)

    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)  # tese / racional de entrada
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # análise ex-post
    emotions: Mapped[str | None] = mapped_column(String(255), nullable=True)  # estado emocional (tags livres)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="trades")

    @property
    def unrealized_pnl(self) -> float | None:
        if self.status != "open" or self.current_price is None:
            return None
        if self.direction == "short":
            gross = (self.entry_price - self.current_price) * self.quantity
        else:
            gross = (self.current_price - self.entry_price) * self.quantity
        return gross - self.fees

    @property
    def stop_alert(self) -> str | None:
        """'atingido' se o preço já cruzou o stop, 'perto' se está a <=20% do caminho até lá."""
        if self.status != "open" or self.current_price is None or self.stop_price is None:
            return None
        if self.direction == "short":
            if self.current_price >= self.stop_price:
                return "atingido"
            total_distance = self.stop_price - self.entry_price
            remaining = self.stop_price - self.current_price
        else:
            if self.current_price <= self.stop_price:
                return "atingido"
            total_distance = self.entry_price - self.stop_price
            remaining = self.current_price - self.stop_price
        if total_distance <= 0:
            return None
        if remaining <= 0.2 * total_distance:
            return "perto"
        return None


class MarketNote(Base):
    __tablename__ = "market_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    date: Mapped[datetime.datetime] = mapped_column(DateTime)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="market_notes")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    date: Mapped[datetime.datetime] = mapped_column(DateTime)
    mood: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ex: confiante, ansioso, disciplinado
    discipline_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="journal_entries")


class RiskSettings(Base):
    __tablename__ = "risk_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    capital_alocado: Mapped[float] = mapped_column(Float)
    budget_anual_pnl: Mapped[float] = mapped_column(Float)
    sharpe_meta: Mapped[float] = mapped_column(Float)

    stop_loss_anual: Mapped[float] = mapped_column(Float)  # também usado como max drawdown anual
    stop_loss_mensal: Mapped[float] = mapped_column(Float)
    stop_loss_diario: Mapped[float] = mapped_column(Float)

    risco_max_tese: Mapped[float] = mapped_column(Float)
    risco_max_classe: Mapped[float] = mapped_column(Float)
    max_trades_simultaneos: Mapped[int] = mapped_column(Integer)
    max_teses_simultaneas: Mapped[int] = mapped_column(Integer)

    behavioral_rules: Mapped[str] = mapped_column(Text, default="[]")  # JSON: list[str]

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="risk_settings")


class ConvictionTier(Base):
    __tablename__ = "conviction_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    label: Mapped[str] = mapped_column(String(32))  # baixa | media | alta | extrema
    pct_of_stop_anual: Mapped[float] = mapped_column(Float)  # 0-1
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="conviction_tiers")


class StopLayer(Base):
    __tablename__ = "stop_layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    level: Mapped[str] = mapped_column(String(16))  # diario | mensal
    alerta_amarelo: Mapped[float] = mapped_column(Float)
    stop_duro: Mapped[float] = mapped_column(Float)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="stop_layers")


class DrawdownPhase(Base):
    __tablename__ = "drawdown_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    pnl_min: Mapped[float] = mapped_column(Float)
    pnl_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # null = sem teto ("+")
    drawdown_max_pct: Mapped[float] = mapped_column(Float)  # 0-1, % do PnL construído
    floor_minimo: Mapped[float] = mapped_column(Float)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="drawdown_phases")


class SeasonalPosture(Base):
    __tablename__ = "seasonal_postures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    periodo: Mapped[str] = mapped_column(String(64))
    situacao_pnl: Mapped[str] = mapped_column(String(128))
    postura: Mapped[str] = mapped_column(String(255))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="seasonal_postures")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    endpoint: Mapped[str] = mapped_column(String(512), unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="push_subscriptions")
