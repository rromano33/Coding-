import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import DailyNote, Trade, User
from app.schemas import DailyNoteCreate, DailyNotePrefill, DailyNoteRead, DailyNoteUpdate
from app.types_labels import MARKET_LABELS, RISK_CLASS_LABELS

router = APIRouter(prefix="/daily-notes", tags=["daily-notes"])


def _format_brl(value: float) -> str:
    s = f"{value:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


@router.get("", response_model=list[DailyNoteRead])
def list_daily_notes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(DailyNote)
        .filter(DailyNote.user_id == current_user.id)
        .order_by(DailyNote.date.desc())
        .all()
    )


@router.get("/prefill", response_model=DailyNotePrefill)
def prefill(
    date: datetime.date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    previous = (
        db.query(DailyNote)
        .filter(DailyNote.user_id == current_user.id, DailyNote.date < datetime.datetime.combine(date, datetime.time.min))
        .order_by(DailyNote.date.desc())
        .first()
    )
    ontem = previous.espero_amanha if previous else None

    day_start = datetime.datetime.combine(date, datetime.time.min)
    day_end = datetime.datetime.combine(date, datetime.time.max)
    closed_today = (
        db.query(Trade)
        .filter(
            Trade.user_id == current_user.id,
            Trade.status == "closed",
            Trade.pnl.isnot(None),
            Trade.exit_date >= day_start,
            Trade.exit_date <= day_end,
        )
        .all()
    )
    totals: dict[str, float] = defaultdict(float)
    for trade in closed_today:
        key = trade.risk_class or "other"
        totals[key] += trade.pnl

    order = ["rates", "fx", "equities", "other"]
    parts = []
    for key in order:
        if key in totals:
            label = RISK_CLASS_LABELS.get(key, key.upper())
            parts.append(f"{label}: R$ {_format_brl(totals[key])}")
    total_pnl = sum(totals.values())
    pnl_por_classe = f"Total: R$ {_format_brl(total_pnl)} | " + " | ".join(parts) if parts else None

    open_trades = (
        db.query(Trade)
        .filter(Trade.user_id == current_user.id, Trade.status == "open")
        .order_by(Trade.entry_date.asc())
        .all()
    )
    lines = []
    for trade in open_trades:
        direction_label = "Long" if trade.direction == "long" else "Short"
        market_label = MARKET_LABELS.get(trade.market, trade.market)
        line = f"- {direction_label} {trade.asset} ({market_label})"
        if trade.thesis:
            line += f" — {trade.thesis.splitlines()[0][:120]}"
        lines.append(line)
    posicoes = "\n".join(lines) if lines else None

    return DailyNotePrefill(ontem=ontem, pnl_por_classe=pnl_por_classe, posicoes=posicoes)


@router.get("/{note_id}", response_model=DailyNoteRead)
def get_daily_note(note_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    note = db.query(DailyNote).filter(DailyNote.id == note_id, DailyNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return note


@router.post("", response_model=DailyNoteRead, status_code=201)
def create_daily_note(
    payload: DailyNoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    note = DailyNote(user_id=current_user.id, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.put("/{note_id}", response_model=DailyNoteRead)
def update_daily_note(
    note_id: int,
    payload: DailyNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(DailyNote).filter(DailyNote.id == note_id, DailyNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
def delete_daily_note(note_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    note = db.query(DailyNote).filter(DailyNote.id == note_id, DailyNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    db.delete(note)
    db.commit()
