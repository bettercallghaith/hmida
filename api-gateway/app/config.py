"""Configuration settings for the API Gateway."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "whatsapp_mcp"
    postgres_user: str = "whatsapp"
    postgres_password: str = "change_me_in_production"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # WhatsApp Engine
    whatsapp_engine_url: str = "http://localhost:3001"

    # Security
    api_secret_key: str = "generate_a_secure_random_string_here"
    api_key_prefix: str = "wamcp_"

    # Rate Limiting
    rate_limit_requests_per_minute: int = 100

    # Logging
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """Get async database URL."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def sync_database_url(self) -> str:
        """Get sync database URL for migrations."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """Get Redis URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
