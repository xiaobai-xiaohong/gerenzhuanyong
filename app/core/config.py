import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Mnemosyne v5.2"
    version: str = "5.2.0"
    api_prefix: str = "/api/v5"

    # Storage
    storage_strategy: str = os.getenv("STORAGE_STRATEGY", "auto")
    db_path: str = os.getenv("DB_PATH", "/data/postgres")
    zvec_path: str = os.getenv("ZVEC_PATH", "/data/zvec")

    # Database
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "mnemosyne")
    postgres_user: str = os.getenv("POSTGRES_USER", "mnemosyne")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "mnemosyne-secret")

    # Redis
    redis_addr: str = os.getenv("REDIS_ADDR", "redis:6379")

    # Model
    model_api_key: str = os.getenv("MODEL_API_KEY", "")
    default_model_tier: str = os.getenv("DEFAULT_MODEL_TIER", "light")

    # Security
    api_key: str = os.getenv("MNEMOSYNE_API_KEY", "mnemosyne-api-key-change-me")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
