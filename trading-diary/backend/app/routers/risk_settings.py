import json
import math

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ConvictionTier, DrawdownPhase, RiskSettings, SeasonalPosture, StopLayer, User
from app.risk_defaults import (
    DEFAULT_BEHAVIORAL_RULES,
    DEFAULT_CONVICTION_TIERS,
    DEFAULT_DRAWDOWN_PHASES,
    DEFAULT_SEASONAL_POSTURES,
    DEFAULT_SETTINGS,
    DEFAULT_STOP_LAYERS,
)
from app.schemas import (
    ConvictionTierItem,
    ConvictionTierRead,
    DrawdownPhaseItem,
    DrawdownPhaseRead,
    RiskSettingsRead,
    RiskSettingsUpdate,
    SeasonalPostureItem,
    SeasonalPostureRead,
    StopLayerItem,
    StopLayerRead,
)

router = APIRouter(prefix="/risk-settings", tags=["risk-settings"])

TRADING_DAYS_PER_YEAR = 252


def get_or_create_settings(db: Session, user: User) -> RiskSettings:
    settings = db.query(RiskSettings).filter(RiskSettings.user_id == user.id).first()
    if settings:
        return settings

    settings = RiskSettings(
        user_id=user.id,
        behavioral_rules=json.dumps(DEFAULT_BEHAVIORAL_RULES, ensure_ascii=False),
        **DEFAULT_SETTINGS,
    )
    db.add(settings)
    db.flush()

    for tier in DEFAULT_CONVICTION_TIERS:
        db.add(ConvictionTier(user_id=user.id, **tier))
    for layer in DEFAULT_STOP_LAYERS:
        db.add(StopLayer(user_id=user.id, **layer))
    for phase in DEFAULT_DRAWDOWN_PHASES:
        db.add(DrawdownPhase(user_id=user.id, **phase))
    for posture in DEFAULT_SEASONAL_POSTURES:
        db.add(SeasonalPosture(user_id=user.id, **posture))

    db.commit()
    db.refresh(settings)
    return settings


def _settings_to_read(settings: RiskSettings) -> RiskSettingsRead:
    vol_anual = settings.budget_anual_pnl / settings.sharpe_meta if settings.sharpe_meta else 0.0
    vol_diaria = vol_anual / math.sqrt(TRADING_DAYS_PER_YEAR)
    return RiskSettingsRead(
        capital_alocado=settings.capital_alocado,
        budget_anual_pnl=settings.budget_anual_pnl,
        sharpe_meta=settings.sharpe_meta,
        stop_loss_anual=settings.stop_loss_anual,
        stop_loss_mensal=settings.stop_loss_mensal,
        stop_loss_diario=settings.stop_loss_diario,
        risco_max_tese=settings.risco_max_tese,
        risco_max_classe=settings.risco_max_classe,
        max_trades_simultaneos=settings.max_trades_simultaneos,
        max_teses_simultaneas=settings.max_teses_simultaneas,
        behavioral_rules=json.loads(settings.behavioral_rules or "[]"),
        vol_anual=vol_anual,
        vol_diaria=vol_diaria,
        updated_at=settings.updated_at,
    )


@router.get("", response_model=RiskSettingsRead)
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = get_or_create_settings(db, current_user)
    return _settings_to_read(settings)


@router.put("", response_model=RiskSettingsRead)
def update_settings(
    payload: RiskSettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    settings = get_or_create_settings(db, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "behavioral_rules" in data:
        settings.behavioral_rules = json.dumps(data.pop("behavioral_rules"), ensure_ascii=False)
    for field, value in data.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return _settings_to_read(settings)


def _risco_maximo(tier: ConvictionTier, settings: RiskSettings) -> float:
    return tier.pct_of_stop_anual * settings.stop_loss_anual


@router.get("/conviction-tiers", response_model=list[ConvictionTierRead])
def list_conviction_tiers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = get_or_create_settings(db, current_user)
    tiers = (
        db.query(ConvictionTier)
        .filter(ConvictionTier.user_id == current_user.id)
        .order_by(ConvictionTier.order_index)
        .all()
    )
    return [
        ConvictionTierRead(
            id=t.id,
            label=t.label,
            pct_of_stop_anual=t.pct_of_stop_anual,
            notes=t.notes,
            order_index=t.order_index,
            risco_maximo=_risco_maximo(t, settings),
        )
        for t in tiers
    ]


@router.put("/conviction-tiers", response_model=list[ConvictionTierRead])
def replace_conviction_tiers(
    items: list[ConvictionTierItem], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    settings = get_or_create_settings(db, current_user)
    db.query(ConvictionTier).filter(ConvictionTier.user_id == current_user.id).delete()
    tiers = [ConvictionTier(user_id=current_user.id, **item.model_dump()) for item in items]
    db.add_all(tiers)
    db.commit()
    for t in tiers:
        db.refresh(t)
    return [
        ConvictionTierRead(
            id=t.id,
            label=t.label,
            pct_of_stop_anual=t.pct_of_stop_anual,
            notes=t.notes,
            order_index=t.order_index,
            risco_maximo=_risco_maximo(t, settings),
        )
        for t in sorted(tiers, key=lambda x: x.order_index)
    ]


@router.get("/stop-layers", response_model=list[StopLayerRead])
def list_stop_layers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_or_create_settings(db, current_user)
    return (
        db.query(StopLayer)
        .filter(StopLayer.user_id == current_user.id)
        .order_by(StopLayer.order_index)
        .all()
    )


@router.put("/stop-layers", response_model=list[StopLayerRead])
def replace_stop_layers(
    items: list[StopLayerItem], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    get_or_create_settings(db, current_user)
    db.query(StopLayer).filter(StopLayer.user_id == current_user.id).delete()
    layers = [StopLayer(user_id=current_user.id, **item.model_dump()) for item in items]
    db.add_all(layers)
    db.commit()
    return sorted(layers, key=lambda x: x.order_index)


@router.get("/drawdown-phases", response_model=list[DrawdownPhaseRead])
def list_drawdown_phases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_or_create_settings(db, current_user)
    return (
        db.query(DrawdownPhase)
        .filter(DrawdownPhase.user_id == current_user.id)
        .order_by(DrawdownPhase.order_index)
        .all()
    )


@router.put("/drawdown-phases", response_model=list[DrawdownPhaseRead])
def replace_drawdown_phases(
    items: list[DrawdownPhaseItem], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    get_or_create_settings(db, current_user)
    db.query(DrawdownPhase).filter(DrawdownPhase.user_id == current_user.id).delete()
    phases = [DrawdownPhase(user_id=current_user.id, **item.model_dump()) for item in items]
    db.add_all(phases)
    db.commit()
    return sorted(phases, key=lambda x: x.order_index)


@router.get("/seasonal-postures", response_model=list[SeasonalPostureRead])
def list_seasonal_postures(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_or_create_settings(db, current_user)
    return (
        db.query(SeasonalPosture)
        .filter(SeasonalPosture.user_id == current_user.id)
        .order_by(SeasonalPosture.order_index)
        .all()
    )


@router.put("/seasonal-postures", response_model=list[SeasonalPostureRead])
def replace_seasonal_postures(
    items: list[SeasonalPostureItem], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    get_or_create_settings(db, current_user)
    db.query(SeasonalPosture).filter(SeasonalPosture.user_id == current_user.id).delete()
    postures = [SeasonalPosture(user_id=current_user.id, **item.model_dump()) for item in items]
    db.add_all(postures)
    db.commit()
    return sorted(postures, key=lambda x: x.order_index)
