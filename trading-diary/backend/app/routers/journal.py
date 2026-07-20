from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import JournalEntry, User
from app.schemas import JournalEntryCreate, JournalEntryRead, JournalEntryUpdate

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("", response_model=list[JournalEntryRead])
def list_journal_entries(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == current_user.id)
        .order_by(JournalEntry.date.desc())
        .all()
    )


@router.post("", response_model=JournalEntryRead, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    entry = JournalEntry(user_id=current_user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{entry_id}", response_model=JournalEntryRead)
def update_journal_entry(
    entry_id: int,
    payload: JournalEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_journal_entry(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    db.delete(entry)
    db.commit()
