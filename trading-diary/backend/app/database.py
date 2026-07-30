from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_database_url = settings.resolved_database_url

if _database_url.startswith("sqlite:///"):
    # Arquivo local (dev). Turso (sqlite+libsql://) não tem path de arquivo
    # pra criar — cai no branch genérico abaixo.
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
