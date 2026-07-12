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
    model_provider: str = os.getenv("MODEL_PROVIDER", "minimax")  # minimax | deepseek | siliconflow | tfidf | auto
    model_api_key: str = os.getenv("MODEL_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    siliconflow_base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn")
    siliconflow_model: str = os.getenv("SILICONFLOW_MODEL", "BAAI/bge-m3")
    default_model_tier: str = os.getenv("DEFAULT_MODEL_TIER", "light")

    # LLM (for auto-extraction)
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Auto-extract
    auto_extract_enabled: bool = os.getenv("AUTO_EXTRACT_ENABLED", "true").lower() == "true"
    auto_extract_interval: int = int(os.getenv("AUTO_EXTRACT_INTERVAL", "3600"))  # seconds
    auto_extract_min_messages: int = int(os.getenv("AUTO_EXTRACT_MIN_MESSAGES", "5"))

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
