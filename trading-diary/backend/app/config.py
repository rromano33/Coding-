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

    # Turso (produção): se ambos setados, substitui o SQLite de arquivo local.
    turso_database_url: str = os.environ.get("TURSO_DATABASE_URL", "")
    turso_auth_token: str = os.environ.get("TURSO_AUTH_TOKEN", "")

    # Segredo compartilhado com o workflow do GitHub Actions que dispara
    # POST /push/run-daily-reminder (gatilho externo, ver app/routers/push.py).
    cron_secret: str = os.environ.get("CRON_SECRET", "")

    class Config:
        env_file = ".env"

    @property
    def use_turso(self) -> bool:
        return bool(self.turso_database_url and self.turso_auth_token)

    @property
    def resolved_database_url(self) -> str:
        # authToken NÃO vai na URL: o driver libsql_experimental só aceita via
        # connect_args (auth_token=...), embutir na query string dá 401
        # "empty JWT token" mesmo com o token certo. Ver database.py.
        if self.use_turso:
            return f"sqlite+libsql://{self.turso_database_url}?secure=true"
        return self.database_url


settings = Settings()
