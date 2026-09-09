import datetime
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PushSubscription, User

logger = logging.getLogger(__name__)


def send_push(db: Session, subscription: PushSubscription, title: str, body: str, url: str = "/") -> bool:
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
    """Roda 1x/dia (~17:30): lembra de escrever uma entrada no diário hoje.

    Repurpose do pivot 2026-09-09 (ver CLAUDE.md) — antes mandava resumo de
    risco/stops; o app não opera mais risco por trades, então virou um
    lembrete simples de hábito, sem depender de nenhum dado financeiro.
    Sempre manda (não checa se já escreveu hoje) — mesma lógica de sempre
    mandar algo que o antigo fallback "trades abertos" já tinha.
    """
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

        title = "Diário"
        body = "Como foi o dia? Escreve uma entrada no diário antes de fechar."
        for subscription in subscriptions:
            send_push(db, subscription, title, body)


def send_morning_reminder(db: Session) -> None:
    """Roda 1x/dia de manhã (~9h): lembra de escrever no diário.

    Repurpose do pivot 2026-09-09 (ver CLAUDE.md) — antes lembrava de
    lançar o resultado oficial de ontem por classe (Rates/FX/Equities/
    Other) pro motor de risco; esse conceito não existe mais. Pula o
    usuário se ele já escreveu alguma entrada hoje (mesma lógica de "pular
    se já preenchido" do reminder antigo, só que contra `JournalEntry` em
    vez de `DailyNote.pnl_*`).
    """
    from app.models import JournalEntry  # import tardio: evita ciclo de import no startup

    user_ids = {row[0] for row in db.query(PushSubscription.user_id).distinct().all()}
    if not user_ids:
        return

    today_start = datetime.datetime.combine(datetime.datetime.utcnow().date(), datetime.time.min)

    for user_id in user_ids:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            continue

        subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
        if not subscriptions:
            continue

        wrote_today = (
            db.query(JournalEntry)
            .filter(JournalEntry.user_id == user_id, JournalEntry.created_at >= today_start)
            .first()
            is not None
        )
        if wrote_today:
            continue

        title = "Bom dia"
        body = "Não esquece de escrever no diário hoje."
        for subscription in subscriptions:
            send_push(db, subscription, title, body)
