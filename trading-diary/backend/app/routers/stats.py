import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Trade, User
from app.schemas import BreakdownItem, EquityCurvePoint, PerformanceSummary

router = APIRouter(prefix="/stats", tags=["stats"])


def _closed_trades(db: Session, user_id: int) -> list[Trade]:
    return (
        db.query(Trade)
        .filter(Trade.user_id == user_id, Trade.status == "closed", Trade.pnl.isnot(None))
        .order_by(Trade.exit_date.asc())
        .all()
    )


def _max_drawdown(ordered_pnls: list[float]) -> float | None:
    if not ordered_pnls:
        return None
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in ordered_pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


@router.get("/summary", response_model=PerformanceSummary)
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_trades = db.query(Trade).filter(Trade.user_id == current_user.id).count()
    closed = _closed_trades(db, current_user.id)
    closed_count = len(closed)

    pnls = [t.pnl for t in closed if t.pnl is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    r_multiples = [t.r_multiple for t in closed if t.r_multiple is not None]

    win_rate = (len(wins) / closed_count) if closed_count else None
    avg_win = (sum(wins) / len(wins)) if wins else None
    avg_loss = (sum(losses) / len(losses)) if losses else None
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None
    expectancy = (sum(pnls) / len(pnls)) if pnls else None
    avg_r = (sum(r_multiples) / len(r_multiples)) if r_multiples else None

    return PerformanceSummary(
        total_trades=total_trades,
        closed_trades=closed_count,
        open_trades=total_trades - closed_count,
        total_pnl=sum(pnls) if pnls else 0.0,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
        avg_r_multiple=avg_r,
        best_trade_pnl=max(pnls) if pnls else None,
        worst_trade_pnl=min(pnls) if pnls else None,
        max_drawdown=_max_drawdown(pnls),
    )


@router.get("/equity-curve", response_model=list[EquityCurvePoint])
def equity_curve(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    closed = _closed_trades(db, current_user.id)

    by_day: dict[datetime.date, list[float]] = defaultdict(list)
    for trade in closed:
        day = (trade.exit_date or trade.entry_date).date()
        by_day[day].append(trade.pnl)

    points: list[EquityCurvePoint] = []
    cumulative = 0.0
    for day in sorted(by_day.keys()):
        day_pnls = by_day[day]
        cumulative += sum(day_pnls)
        points.append(EquityCurvePoint(date=day, cumulative_pnl=cumulative, trade_count=len(day_pnls)))
    return points


def _breakdown_by(closed: list[Trade], key_fn) -> list[BreakdownItem]:
    groups: dict[str, list[float]] = defaultdict(list)
    for trade in closed:
        key = key_fn(trade) or "(sem categoria)"
        groups[key].append(trade.pnl)

    items = []
    for key, pnls in groups.items():
        wins = [p for p in pnls if p > 0]
        items.append(
            BreakdownItem(
                key=key,
                trade_count=len(pnls),
                total_pnl=sum(pnls),
                win_rate=(len(wins) / len(pnls)) if pnls else None,
            )
        )
    return sorted(items, key=lambda i: i.total_pnl, reverse=True)


@router.get("/by-strategy", response_model=list[BreakdownItem])
def by_strategy(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    closed = _closed_trades(db, current_user.id)
    return _breakdown_by(closed, lambda t: t.strategy)


@router.get("/by-asset", response_model=list[BreakdownItem])
def by_asset(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    closed = _closed_trades(db, current_user.id)
    return _breakdown_by(closed, lambda t: t.asset)


@router.get("/by-market", response_model=list[BreakdownItem])
def by_market(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    closed = _closed_trades(db, current_user.id)
    return _breakdown_by(closed, lambda t: t.market)
