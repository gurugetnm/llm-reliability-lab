"""Application configuration, loaded from environment variables / `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the API.

    All values have sane local-development defaults so the app can start
    without a `.env` file; production deployments should override every
    value that matters (especially `database_url`).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "LLM Reliability Lab API"
    environment: str = "development"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://llm_lab:llm_lab@localhost:5432/llm_reliability_lab"

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    # --- LLM providers ---
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — environment variables are read once."""
    return Settings()
