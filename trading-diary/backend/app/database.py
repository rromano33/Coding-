from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_database_url = settings.resolved_database_url

if settings.use_turso:
    # authToken tem que ir via connect_args (auth_token=...), não na URL —
    # ver comentário em config.py:resolved_database_url.
    engine = create_engine(_database_url, connect_args={"auth_token": settings.turso_auth_token})
elif _database_url.startswith("sqlite:///"):
    # Arquivo local (dev).
    Path(_database_url.split("///")[-1]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(_database_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(_database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
