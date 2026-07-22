import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.calculations import apply_computed_fields
from app.database import get_db
from app.models import Trade, User
from app.schemas import TradeCreate, TradePriceUpdate, TradeRead, TradeUpdate

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=list[TradeRead])
def list_trades(
    status: str | None = None,
    asset: str | None = None,
    strategy: str | None = None,
    market: str | None = None,
    date_from: datetime.datetime | None = None,
    date_to: datetime.datetime | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Trade).filter(Trade.user_id == current_user.id)
    if status:
        query = query.filter(Trade.status == status)
    if asset:
        query = query.filter(Trade.asset.ilike(f"%{asset}%"))
    if strategy:
        query = query.filter(Trade.strategy.ilike(f"%{strategy}%"))
    if market:
        query = query.filter(Trade.market == market)
    if date_from:
        query = query.filter(Trade.entry_date >= date_from)
    if date_to:
        query = query.filter(Trade.entry_date <= date_to)
    return query.order_by(Trade.entry_date.desc()).all()


@router.get("/{trade_id}", response_model=TradeRead)
def get_trade(trade_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    return trade


@router.post("", response_model=TradeRead, status_code=201)
def create_trade(payload: TradeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trade = Trade(user_id=current_user.id, **payload.model_dump())
    apply_computed_fields(trade)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.put("/{trade_id}", response_model=TradeRead)
def update_trade(
    trade_id: int,
    payload: TradeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade não encontrado")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trade, field, value)

    apply_computed_fields(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.patch("/{trade_id}/price", response_model=TradeRead)
def update_price(
    trade_id: int,
    payload: TradePriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    trade.current_price = payload.current_price
    trade.current_price_updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    trade = db.query(Trade).filter(Trade.id == trade_id, Trade.user_id == current_user.id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade não encontrado")
    db.delete(trade)
    db.commit()
