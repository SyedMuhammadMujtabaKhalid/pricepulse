"""
PricePulse — Application Settings
==================================

Central configuration management using Pydantic Settings.

Engineering Decisions:
    1. pydantic-settings reads from environment variables and .env files automatically.
       This follows the 12-Factor App methodology (config via environment).
    2. All settings have sensible defaults for local development.
       Production overrides happen via environment variables — zero code changes needed.
    3. Settings are validated at application startup. If DATABASE_URL is malformed or
       a required variable is missing, the app fails fast with a clear error.
    4. The Settings class is instantiated once (via get_settings) and reused everywhere.
       This avoids reading .env files on every function call.

Usage:
    from config.settings import get_settings
    settings = get_settings()
    print(settings.database_url)
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory (one level up from config/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application configuration.

    Values are loaded in this priority order (highest wins):
        1. Environment variables
        2. .env file
        3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (e.g. PGADMIN_*)
    )

    # ── Database ──────────────────────────────────────────────
    postgres_user: str = Field(default="pricepulse", description="PostgreSQL username")
    postgres_password: str = Field(
        default="pricepulse_secret", description="PostgreSQL password"
    )
    postgres_db: str = Field(
        default="pricepulse", description="PostgreSQL database name"
    )
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    database_url: str | None = Field(
        default=None,
        description="Full database URL. If not set, constructed from components.",
    )

    # ── Application ───────────────────────────────────────────
    app_env: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="console",
        description="Log output format: 'console' (human) or 'json' (machine)",
    )

    # ── Pipeline ──────────────────────────────────────────────
    pipeline_retry_attempts: int = Field(
        default=3, description="Number of retry attempts for failed extractions"
    )
    pipeline_retry_delay_seconds: int = Field(
        default=2, description="Base delay between retries (exponential backoff)"
    )

    # ── Scraper ───────────────────────────────────────────────
    scraper_headless: bool = Field(
        default=True, description="Run browser in headless mode"
    )
    scraper_timeout_ms: int = Field(
        default=30000, description="Browser navigation timeout in milliseconds"
    )

    # ── Validators ────────────────────────────────────────────

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return upper

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Ensure environment is valid."""
        allowed = {"development", "staging", "production"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"app_env must be one of {allowed}, got '{v}'")
        return lower

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Ensure log format is valid."""
        allowed = {"console", "json"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"log_format must be one of {allowed}, got '{v}'")
        return lower

    # ── Computed Properties ───────────────────────────────────

    def get_database_url(self) -> str:
        """
        Return the database connection URL.

        If DATABASE_URL is explicitly set, use it directly.
        Otherwise, construct it from individual components.

        Why this pattern?
            - Local dev uses components (easy to change host/port/db independently)
            - Production uses DATABASE_URL (provided by cloud platforms like Heroku, Render)
            - Both work without code changes
        """
        if self.database_url:
            return self.database_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Why lru_cache?
        Settings are read from .env and environment variables, which involves
        disk I/O. Caching ensures we only do this once per process lifetime.
        Every call to get_settings() returns the same instance.
    """
    return Settings()
