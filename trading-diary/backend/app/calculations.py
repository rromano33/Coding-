from app.models import Trade


def compute_pnl(trade: Trade) -> float | None:
    if trade.exit_price is None:
        return None
    if trade.direction == "short":
        gross = (trade.entry_price - trade.exit_price) * trade.quantity
    else:
        gross = (trade.exit_price - trade.entry_price) * trade.quantity
    return gross - trade.fees


def compute_r_multiple(trade: Trade, pnl: float | None) -> float | None:
    if pnl is None or trade.stop_price is None:
        return None
    risk_per_unit = abs(trade.entry_price - trade.stop_price)
    if risk_per_unit == 0:
        return None
    risk_amount = risk_per_unit * trade.quantity
    return pnl / risk_amount


def apply_computed_fields(trade: Trade) -> None:
    trade.pnl = compute_pnl(trade)
    trade.r_multiple = compute_r_multiple(trade, trade.pnl)
    if trade.exit_price is not None and trade.status == "open":
        trade.status = "closed"
