import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'trading_diary.db'}"
    secret_key: str = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    access_token_expire_minutes: int = 60 * 24 * 30  # 30 dias
    algorithm: str = "HS256"
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
