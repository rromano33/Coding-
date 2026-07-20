from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MarketNote, User
from app.schemas import MarketNoteCreate, MarketNoteRead, MarketNoteUpdate

router = APIRouter(prefix="/market-notes", tags=["market-notes"])


@router.get("", response_model=list[MarketNoteRead])
def list_market_notes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(MarketNote)
        .filter(MarketNote.user_id == current_user.id)
        .order_by(MarketNote.date.desc())
        .all()
    )


@router.post("", response_model=MarketNoteRead, status_code=201)
def create_market_note(
    payload: MarketNoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    note = MarketNote(user_id=current_user.id, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.put("/{note_id}", response_model=MarketNoteRead)
def update_market_note(
    note_id: int,
    payload: MarketNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(MarketNote).filter(MarketNote.id == note_id, MarketNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
def delete_market_note(note_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    note = db.query(MarketNote).filter(MarketNote.id == note_id, MarketNote.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    db.delete(note)
    db.commit()
