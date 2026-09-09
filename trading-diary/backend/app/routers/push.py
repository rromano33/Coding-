from fastapi import APIRouter, Depends, Header, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import PushSubscription, User
from app.push_service import send_daily_reminder, send_morning_reminder, send_push
from app.schemas import PushSubscriptionCreate, PushSubscriptionRemove, VapidPublicKey

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/public-key", response_model=VapidPublicKey)
def public_key():
    if not settings.vapid_public_key:
        raise HTTPException(
            http_status.HTTP_503_SERVICE_UNAVAILABLE, "VAPID_PUBLIC_KEY não configurada no backend"
        )
    return VapidPublicKey(public_key=settings.vapid_public_key)


@router.post("/subscribe", status_code=http_status.HTTP_204_NO_CONTENT)
def subscribe(
    payload: PushSubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        db.add(
            PushSubscription(
                user_id=current_user.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
            )
        )
    db.commit()


@router.post("/unsubscribe", status_code=http_status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: PushSubscriptionRemove, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == payload.endpoint, PushSubscription.user_id == current_user.id
    ).delete()
    db.commit()


@router.post("/test", status_code=http_status.HTTP_204_NO_CONTENT)
def test(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == current_user.id).all()
    if not subscriptions:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Nenhuma subscription de push cadastrada para este usuário")
    for subscription in subscriptions:
        send_push(db, subscription, "Teste", "Notificação de teste do diário.")


@router.post("/run-daily-reminder", status_code=http_status.HTTP_204_NO_CONTENT)
def run_daily_reminder(
    db: Session = Depends(get_db), x_cron_secret: str | None = Header(default=None)
):
    """Gatilho externo pro lembrete diário (GitHub Actions agendado).

    Existe porque em produção (Render free) o processo pode estar
    hibernando no horário do `BackgroundScheduler` in-process — essa
    chamada HTTP externa acorda o serviço e dispara o envio de verdade.
    """
    if not settings.cron_secret:
        raise HTTPException(http_status.HTTP_503_SERVICE_UNAVAILABLE, "CRON_SECRET não configurado no backend")
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(http_status.HTTP_401_UNAUTHORIZED, "Cron secret inválido")
    send_daily_reminder(db)


@router.post("/run-morning-reminder", status_code=http_status.HTTP_204_NO_CONTENT)
def run_morning_reminder(
    db: Session = Depends(get_db), x_cron_secret: str | None = Header(default=None)
):
    """Gatilho externo pro lembrete matinal (~9h) de escrever no diário."""
    if not settings.cron_secret:
        raise HTTPException(http_status.HTTP_503_SERVICE_UNAVAILABLE, "CRON_SECRET não configurado no backend")
    if x_cron_secret != settings.cron_secret:
        raise HTTPException(http_status.HTTP_401_UNAUTHORIZED, "Cron secret inválido")
    send_morning_reminder(db)
