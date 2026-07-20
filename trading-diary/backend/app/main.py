from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import auth, journal, market_notes, stats, trades

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading Diary API", version="0.1.0")

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


@app.get("/health")
def health():
    return {"status": "ok"}
