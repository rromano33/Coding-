from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Trade


def gross_pnl(direction: str, entry_price: float, exit_price: float, quantity: float, multiplier: float = 1.0) -> float:
    if direction == "short":
        diff = entry_price - exit_price
    else:
        diff = exit_price - entry_price
    return diff * quantity * multiplier


def _fx_rate(trade: "Trade") -> float:
    if trade.currency and trade.currency.upper() != "BRL" and trade.fx_rate_to_brl:
        return trade.fx_rate_to_brl
    return 1.0


def compute_pnl(trade: "Trade") -> float | None:
    if trade.exit_price is None:
        return None
    gross = gross_pnl(trade.direction, trade.entry_price, trade.exit_price, trade.quantity, trade.contract_multiplier or 1.0)
    net = gross - trade.fees
    return net * _fx_rate(trade) + (trade.manual_adjustment or 0.0)


def compute_r_multiple(trade: "Trade", pnl: float | None) -> float | None:
    if pnl is None or trade.stop_price is None:
        return None
    risk_per_unit = abs(trade.entry_price - trade.stop_price)
    if risk_per_unit == 0:
        return None
    risk_amount = risk_per_unit * trade.quantity * (trade.contract_multiplier or 1.0) * _fx_rate(trade)
    if risk_amount == 0:
        return None
    return pnl / risk_amount


def position_risk_brl(trade: "Trade") -> float:
    if trade.stop_price is None:
        return 0.0
    risk = abs(trade.entry_price - trade.stop_price) * trade.quantity * (trade.contract_multiplier or 1.0)
    return risk * _fx_rate(trade)


def apply_computed_fields(trade: "Trade") -> None:
    trade.pnl = compute_pnl(trade)
    trade.r_multiple = compute_r_multiple(trade, trade.pnl)
    if trade.exit_price is not None and trade.status == "open":
        trade.status = "closed"
