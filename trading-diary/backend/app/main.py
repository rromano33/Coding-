import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.push_service import send_daily_reminder
from app.routers import auth, journal, market_notes, push, risk, risk_settings, stats, trades

Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()


def _run_daily_reminder_job() -> None:
    db = SessionLocal()
    try:
        send_daily_reminder(db)
    finally:
        db.close()


_ENABLE_INTERNAL_SCHEDULER = os.environ.get("ENABLE_INTERNAL_SCHEDULER", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Em produção (Render free) o processo pode estar hibernando às 17:30 e
    # esse scheduler in-process simplesmente não roda — o gatilho real de
    # produção é o GitHub Actions batendo em POST /push/run-daily-reminder
    # (acorda o Render sozinho). Deixar essa env var unset/false no Render
    # evita mandar push duplicado nos dias em que o processo por acaso já
    # estiver acordado no horário. Local dev mantém default true.
    if _ENABLE_INTERNAL_SCHEDULER:
        scheduler.add_job(
            _run_daily_reminder_job,
            "cron",
            hour=17,
            minute=30,
            timezone="America/Sao_Paulo",
            id="daily_reminder",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(title="Trading Diary API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(trades.router)
app.include_router(market_notes.router)
app.include_router(journal.router)
app.include_router(stats.router)
app.include_router(risk_settings.router)
app.include_router(risk.router)
app.include_router(push.router)


@app.get("/health")
def health():
    return {"status": "ok"}
