import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PushSubscription, User

logger = logging.getLogger(__name__)


def send_push(db: Session, subscription: PushSubscription, title: str, body: str, url: str = "/risco") -> bool:
    """Manda uma notificação push. Remove a subscription do banco se o endpoint não existir mais (410/404)."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_claim_email}"},
        )
        return True
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (404, 410):
            db.delete(subscription)
            db.commit()
        else:
            logger.warning("Falha ao enviar push para %s: %s", subscription.endpoint, exc)
        return False


def send_daily_reminder(db: Session) -> None:
    """Roda 1x/dia: manda um resumo de risco (ou lembrete simples) pra cada usuário com push ativo."""
    from app.routers.risk import status as risk_status  # import tardio: evita ciclo de import no startup

    user_ids = {row[0] for row in db.query(PushSubscription.user_id).distinct().all()}
    if not user_ids:
        return

    for user_id in user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            continue

        subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
        if not subscriptions:
            continue

        risk = risk_status(db=db, current_user=user)
        stops = [a for a in risk.alerts if a.severity == "stop"]
        alertas = [a for a in risk.alerts if a.severity == "alerta"]

        if stops:
            title = "🛑 Stop atingido"
            body = stops[0].message if len(stops) == 1 else f"{len(stops)} stops atingidos. {stops[0].message}"
        elif alertas:
            title = "⚠️ Alerta de risco"
            body = alertas[0].message if len(alertas) == 1 else f"{len(alertas)} alertas ativos. {alertas[0].message}"
        else:
            title = "Diário de trades"
            body = f"{risk.trades_abertos} trade(s) aberto(s). Bora marcar preços e revisar o risco do dia."

        for subscription in subscriptions:
            send_push(db, subscription, title, body)
