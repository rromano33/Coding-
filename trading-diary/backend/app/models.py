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

    strategy: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)  # comma-separated

    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)

    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)  # tese / racional de entrada
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # análise ex-post
    emotions: Mapped[str | None] = mapped_column(String(255), nullable=True)  # estado emocional (tags livres)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="trades")


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
