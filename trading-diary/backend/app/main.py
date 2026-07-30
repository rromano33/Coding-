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


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_run_daily_reminder_job, "cron", hour=9, minute=0, id="daily_reminder", replace_existing=True)
    scheduler.start()
    yield
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
