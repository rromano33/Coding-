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

    vapid_public_key: str = os.environ.get("VAPID_PUBLIC_KEY", "")
    vapid_private_key: str = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_claim_email: str = os.environ.get("VAPID_CLAIM_EMAIL", "ricardo.fipe@gmail.com")

    class Config:
        env_file = ".env"


settings = Settings()
