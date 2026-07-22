import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ConvictionTier, DrawdownPhase, StopLayer, Trade, User
from app.routers.risk_settings import get_or_create_settings
from app.schemas import ConcentrationItem, RiskAlert, RiskStatus

router = APIRouter(prefix="/risk", tags=["risk"])


def _position_risk(trade: Trade) -> float:
    if trade.stop_price is None:
        return 0.0
    return abs(trade.entry_price - trade.stop_price) * trade.quantity


def _concentration(open_trades: list[Trade], key_fn, limite: float) -> list[ConcentrationItem]:
    groups: dict[str, float] = defaultdict(float)
    for trade in open_trades:
        key = key_fn(trade) or "(sem categoria)"
        groups[key] += _position_risk(trade)
    return [
        ConcentrationItem(key=key, risco_atual=risco, limite=limite, over=risco > limite)
        for key, risco in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
    ]


@router.get("/status", response_model=RiskStatus)
def status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = get_or_create_settings(db, current_user)
    tiers = {t.label: t for t in db.query(ConvictionTier).filter(ConvictionTier.user_id == current_user.id).all()}
    stop_layers = {
        layer.level: layer for layer in db.query(StopLayer).filter(StopLayer.user_id == current_user.id).all()
    }
    phases = (
        db.query(DrawdownPhase)
        .filter(DrawdownPhase.user_id == current_user.id)
        .order_by(DrawdownPhase.order_index)
        .all()
    )

    all_trades = db.query(Trade).filter(Trade.user_id == current_user.id).all()
    open_trades = [t for t in all_trades if t.status == "open"]
    closed = sorted(
        (t for t in all_trades if t.status == "closed" and t.exit_date is not None and t.pnl is not None),
        key=lambda t: t.exit_date,
    )

    now = datetime.datetime.utcnow()
    today = now.date()

    pnl_today = sum(t.pnl for t in closed if t.exit_date.date() == today)
    pnl_month = sum(t.pnl for t in closed if (t.exit_date.year, t.exit_date.month) == (today.year, today.month))
    year_trades = [t for t in closed if t.exit_date.year == today.year]
    pnl_year = sum(t.pnl for t in year_trades)

    cumulative = 0.0
    peak = 0.0
    for t in year_trades:
        cumulative += t.pnl
        peak = max(peak, cumulative)
    drawdown_atual = max(0.0, peak - cumulative)

    phase = next(
        (p for p in phases if p.pnl_min <= pnl_year and (p.pnl_max is None or pnl_year < p.pnl_max)), None
    )
    drawdown_permitido = None
    drawdown_floor_minimo = None
    phase_label = None
    if phase:
        drawdown_permitido = max(phase.drawdown_max_pct * pnl_year, phase.floor_minimo)
        drawdown_floor_minimo = phase.floor_minimo
        max_label = f"R${phase.pnl_max / 1_000_000:.0f}M" if phase.pnl_max is not None else "+"
        phase_label = f"R${phase.pnl_min / 1_000_000:.0f}M–{max_label}"

    teses_abertas_set = {t.strategy for t in open_trades if t.strategy}

    concentracao_tese = _concentration(open_trades, lambda t: t.strategy, settings.risco_max_tese)
    concentracao_classe = _concentration(open_trades, lambda t: t.market, settings.risco_max_classe)

    alerts: list[RiskAlert] = []

    def check_stop(label: str, loss: float, layer: StopLayer | None, fallback_limit: float):
        if layer:
            if loss >= layer.stop_duro:
                alerts.append(RiskAlert(severity="stop", message=f"Stop {label} atingido: perda de R$ {loss:,.0f} (limite R$ {layer.stop_duro:,.0f})."))
            elif loss >= layer.alerta_amarelo:
                alerts.append(RiskAlert(severity="alerta", message=f"Alerta {label}: perda de R$ {loss:,.0f} (alerta em R$ {layer.alerta_amarelo:,.0f})."))
        elif loss >= fallback_limit:
            alerts.append(RiskAlert(severity="stop", message=f"Stop {label} atingido: perda de R$ {loss:,.0f} (limite R$ {fallback_limit:,.0f})."))

    check_stop("diário", max(0.0, -pnl_today), stop_layers.get("diario"), settings.stop_loss_diario)
    check_stop("mensal", max(0.0, -pnl_month), stop_layers.get("mensal"), settings.stop_loss_mensal)

    loss_year = max(0.0, -pnl_year)
    if loss_year >= settings.stop_loss_anual:
        alerts.append(
            RiskAlert(severity="stop", message=f"Stop anual atingido: perda de R$ {loss_year:,.0f} (limite R$ {settings.stop_loss_anual:,.0f}).")
        )

    if drawdown_permitido is not None and drawdown_atual > drawdown_permitido:
        alerts.append(
            RiskAlert(
                severity="stop",
                message=f"Drawdown do ano (R$ {drawdown_atual:,.0f}) acima do permitido para a fase {phase_label} (R$ {drawdown_permitido:,.0f}).",
            )
        )

    if len(open_trades) > settings.max_trades_simultaneos:
        alerts.append(
            RiskAlert(severity="alerta", message=f"{len(open_trades)} trades abertos, acima do limite de {settings.max_trades_simultaneos}.")
        )
    if len(teses_abertas_set) > settings.max_teses_simultaneas:
        alerts.append(
            RiskAlert(severity="alerta", message=f"{len(teses_abertas_set)} teses abertas, acima do limite de {settings.max_teses_simultaneas}.")
        )

    for item in concentracao_tese:
        if item.over:
            alerts.append(RiskAlert(severity="alerta", message=f"Risco na tese '{item.key}' (R$ {item.risco_atual:,.0f}) acima do limite por tese (R$ {item.limite:,.0f})."))
    for item in concentracao_classe:
        if item.over:
            alerts.append(RiskAlert(severity="alerta", message=f"Risco na classe '{item.key}' (R$ {item.risco_atual:,.0f}) acima do limite por classe (R$ {item.limite:,.0f})."))

    for t in open_trades:
        if t.stop_alert == "atingido":
            alerts.append(
                RiskAlert(
                    severity="stop",
                    message=f"{t.asset}: preço atual (R$ {t.current_price:,.2f}) já cruzou o stop (R$ {t.stop_price:,.2f}).",
                    trade_id=t.id,
                )
            )
        elif t.stop_alert == "perto":
            alerts.append(
                RiskAlert(
                    severity="alerta",
                    message=f"{t.asset}: preço atual (R$ {t.current_price:,.2f}) está próximo do stop (R$ {t.stop_price:,.2f}).",
                    trade_id=t.id,
                )
            )

    for t in open_trades:
        if t.conviction and t.stop_price is not None:
            tier = tiers.get(t.conviction)
            if tier:
                risco_atual = _position_risk(t)
                risco_permitido = tier.pct_of_stop_anual * settings.stop_loss_anual
                if risco_atual > risco_permitido:
                    alerts.append(
                        RiskAlert(
                            severity="alerta",
                            message=f"{t.asset}: risco de R$ {risco_atual:,.0f} excede o máximo para convicção '{t.conviction}' (R$ {risco_permitido:,.0f}).",
                            trade_id=t.id,
                        )
                    )

    return RiskStatus(
        pnl_today=pnl_today,
        pnl_month=pnl_month,
        pnl_year=pnl_year,
        budget_anual_pnl=settings.budget_anual_pnl,
        pct_of_budget_year=(pnl_year / settings.budget_anual_pnl) if settings.budget_anual_pnl else None,
        drawdown_atual=drawdown_atual,
        drawdown_permitido=drawdown_permitido,
        drawdown_floor_minimo=drawdown_floor_minimo,
        drawdown_phase_label=phase_label,
        trades_abertos=len(open_trades),
        max_trades_simultaneos=settings.max_trades_simultaneos,
        teses_abertas=len(teses_abertas_set),
        max_teses_simultaneas=settings.max_teses_simultaneas,
        concentracao_tese=concentracao_tese,
        concentracao_classe=concentracao_classe,
        alerts=alerts,
    )
