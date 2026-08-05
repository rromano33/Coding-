import datetime
import re
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.calculations import position_risk_brl
from app.database import get_db
from app.models import ConvictionTier, DailyNote, DrawdownPhase, SeasonalPosture, StopLayer, Trade, User
from app.routers.risk_settings import get_or_create_settings
from app.schemas import ConcentrationItem, RiskAlert, RiskStatus

router = APIRouter(prefix="/risk", tags=["risk"])

_MES_NUM = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def _periodo_bate(periodo: str, mes_atual: int) -> bool:
    partes = re.split(r"[–-]", periodo.strip())
    meses = [_MES_NUM.get(p.strip()[:3].lower()) for p in partes]
    if any(m is None for m in meses):
        return False
    if len(meses) == 1:
        return mes_atual == meses[0]
    return meses[0] <= mes_atual <= meses[1]


def _situacao_bate(situacao: str, pct_of_budget_year: float | None) -> bool:
    situacao = situacao.strip().lower()
    if situacao == "qualquer":
        return True
    if pct_of_budget_year is None:
        return False
    match = re.search(r"(abaixo|acima) de (\d+(?:\.\d+)?)\s*%", situacao)
    if not match:
        return False
    direcao, valor = match.group(1), float(match.group(2)) / 100
    return pct_of_budget_year < valor if direcao == "abaixo" else pct_of_budget_year >= valor


def _postura_atual(db: Session, user_id: int, pct_of_budget_year: float | None) -> str | None:
    """Postura sazonal que se aplica hoje, cruzando o mês atual com o % da meta
    anual batido — refinamento do 'controle por drawdown' pra virar algo que o
    app de fato avisa, não só uma tabela de referência que o usuário tem que
    conferir manualmente."""
    mes_atual = datetime.datetime.utcnow().month
    posturas = (
        db.query(SeasonalPosture)
        .filter(SeasonalPosture.user_id == user_id)
        .order_by(SeasonalPosture.order_index)
        .all()
    )
    for p in posturas:
        if _periodo_bate(p.periodo, mes_atual) and _situacao_bate(p.situacao_pnl, pct_of_budget_year):
            return f"{p.periodo} · {p.situacao_pnl}: {p.postura}"
    return None


def _concentration(open_trades: list[Trade], key_fn, limite: float) -> list[ConcentrationItem]:
    groups: dict[str, float] = defaultdict(float)
    for trade in open_trades:
        key = key_fn(trade) or "(sem categoria)"
        groups[key] += position_risk_brl(trade)
    return [
        ConcentrationItem(key=key, risco_atual=risco, limite=limite, over=risco > limite)
        for key, risco in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _daily_official_pnl(db: Session, user_id: int) -> list[tuple[datetime.date, float]]:
    """PnL oficial por dia, fonte única de verdade pro risco (stops/drawdown/YTD).

    Vem do resultado top-down lançado no Diário (Rates/FX/Equities/Other), não de
    trades individuais — o usuário decidiu que trades no app servem só pra apoio
    (cálculo de PnL individual, sizing de posição), não pra contabilidade de risco.
    Um dia só entra na conta se pelo menos uma classe tiver sido preenchida.
    """
    notes = db.query(DailyNote).filter(DailyNote.user_id == user_id).all()
    daily: dict[datetime.date, float] = {}
    for note in notes:
        classes = [note.pnl_rates, note.pnl_fx, note.pnl_equities, note.pnl_other]
        if all(c is None for c in classes):
            continue
        daily[note.date.date()] = sum(c or 0.0 for c in classes)
    return sorted(daily.items())


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

    now = datetime.datetime.utcnow()
    today = now.date()

    daily_pnl = _daily_official_pnl(db, current_user.id)

    pnl_today = sum(v for d, v in daily_pnl if d == today)
    pnl_month = sum(v for d, v in daily_pnl if (d.year, d.month) == (today.year, today.month))
    year_days = [(d, v) for d, v in daily_pnl if d.year == today.year]
    pnl_year = sum(v for _, v in year_days)

    cumulative = 0.0
    peak = 0.0
    for _, v in year_days:
        cumulative += v
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

    pct_of_budget_year = (pnl_year / settings.budget_anual_pnl) if settings.budget_anual_pnl else None
    postura_atual = _postura_atual(db, current_user.id, pct_of_budget_year)

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
                risco_atual = position_risk_brl(t)
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
        pct_of_budget_year=pct_of_budget_year,
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
        postura_atual=postura_atual,
        alerts=alerts,
    )
