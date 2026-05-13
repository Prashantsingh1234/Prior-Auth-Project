"""
Application configuration management.

Uses Pydantic Settings to load and validate all configuration from environment
variables and .env files. This is the single source of truth for all runtime config.

Design decisions:
- Pydantic v2 BaseSettings for type-safe config with automatic env loading
- @lru_cache ensures a single settings instance across the app (singleton via DI)
- Computed properties for derived values (database_url, etc.)
- Separate inner classes group related settings logically
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings.

    All fields are loaded from environment variables (case-insensitive).
    Sensitive fields use SecretStr to prevent accidental logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Allow extra fields from .env without raising errors
        extra="ignore",
    )

    # ----------------------------------------------------------
    # Application
    # ----------------------------------------------------------
    app_name: str = Field(default="PA Review Platform", description="Human-readable application name")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development", description="development | staging | production")
    debug: bool = Field(default=False)

    # ----------------------------------------------------------
    # API
    # ----------------------------------------------------------
    api_prefix: str = Field(default="/api/v1")
    api_title: str = Field(default="AI-Assisted Prior Authorization Review Platform")
    allowed_hosts: list[str] = Field(default=["localhost", "127.0.0.1"])

    # ----------------------------------------------------------
    # Security
    # ----------------------------------------------------------
    secret_key: SecretStr = Field(..., description="HMAC signing key — generate with: openssl rand -hex 32")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)

    # ----------------------------------------------------------
    # CORS
    # ----------------------------------------------------------
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    cors_allow_credentials: bool = Field(default=True)

    # ----------------------------------------------------------
    # Database (MySQL)
    # ----------------------------------------------------------
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=3306)
    db_name: str = Field(default="pa_review_db")
    db_user: str = Field(default="pa_user")
    db_password: SecretStr = Field(default=SecretStr("pa_password"))
    db_pool_size: int = Field(default=10, ge=1, le=50)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30)
    db_pool_recycle: int = Field(default=1800, description="Recycle connections after N seconds")
    db_echo: bool = Field(default=False, description="Log SQL queries — never True in production")

    # ----------------------------------------------------------
    # Redis
    # ----------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_password: SecretStr | None = Field(default=None)
    redis_ttl: int = Field(default=3600, description="Default cache TTL in seconds")
    redis_max_connections: int = Field(default=20)

    # ----------------------------------------------------------
    # Pinecone
    # ----------------------------------------------------------
    pinecone_api_key: SecretStr | None = Field(default=None)
    pinecone_environment: str = Field(default="us-east-1-aws")
    pinecone_index_name: str = Field(default="pa-policies")
    pinecone_namespace: str = Field(default="production")

    # ----------------------------------------------------------
    # OpenAI
    # ----------------------------------------------------------
    openai_api_key: SecretStr | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o")
    openai_max_tokens: int = Field(default=4096)
    openai_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    openai_request_timeout: int = Field(default=60)

    # ----------------------------------------------------------
    # Azure AI Document Intelligence (Primary OCR)
    # ----------------------------------------------------------
    azure_document_intelligence_endpoint: str | None = Field(default=None)
    azure_document_intelligence_key: SecretStr | None = Field(default=None)
    # Trigger PaddleOCR fallback when Azure confidence drops below this
    azure_ocr_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    azure_ocr_timeout: int = Field(default=30)

    # ----------------------------------------------------------
    # LangSmith (Tracing & Evaluation)
    # ----------------------------------------------------------
    langsmith_api_key: SecretStr | None = Field(default=None)
    langsmith_project: str = Field(default="pa-review-platform")
    langchain_tracing_v2: bool = Field(default=False)
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com")

    # ----------------------------------------------------------
    # RabbitMQ (Async Queue)
    # ----------------------------------------------------------
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    rabbitmq_pa_queue: str = Field(default="pa.requests")
    rabbitmq_notification_queue: str = Field(default="pa.notifications")
    rabbitmq_prefetch_count: int = Field(default=10)

    # ----------------------------------------------------------
    # Logging
    # ----------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="json | console")

    # ----------------------------------------------------------
    # Rate Limiting
    # ----------------------------------------------------------
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60, description="Window size in seconds")

    # ----------------------------------------------------------
    # Monitoring
    # ----------------------------------------------------------
    prometheus_enabled: bool = Field(default=True)
    prometheus_endpoint: str = Field(default="/metrics")

    # ----------------------------------------------------------
    # File Upload
    # ----------------------------------------------------------
    max_upload_size_bytes: int = Field(
        default=52_428_800,  # 50 MB
        description="Maximum allowed file upload size",
    )
    allowed_upload_extensions: list[str] = Field(
        default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".json", ".txt"]
    )

    # ----------------------------------------------------------
    # Validators
    # ----------------------------------------------------------

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got '{v}'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        allowed = {"json", "console"}
        if v.lower() not in allowed:
            raise ValueError(f"log_format must be one of {allowed}")
        return v.lower()

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce stricter validation when running in production."""
        if self.environment == "production":
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if self.db_echo:
                raise ValueError("DB_ECHO must be False in production — SQL query logging leaks data")
        return self

    # ----------------------------------------------------------
    # Computed Properties
    # ----------------------------------------------------------

    @property
    def database_url(self) -> str:
        """Async-compatible MySQL DSN for SQLAlchemy."""
        password = self.db_password.get_secret_value()
        return (
            f"mysql+aiomysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_staging(self) -> bool:
        return self.environment == "staging"

    @property
    def docs_enabled(self) -> bool:
        """Swagger UI only available outside production."""
        return not self.is_production

    def safe_dict(self) -> dict[str, Any]:
        """
        Return settings as a dict with secrets redacted.
        Safe to log or include in health check responses.
        """
        data = self.model_dump()
        secret_fields = {
            "secret_key", "db_password", "redis_password",
            "pinecone_api_key", "openai_api_key",
            "azure_document_intelligence_key", "langsmith_api_key",
        }
        for field in secret_fields:
            if field in data and data[field] is not None:
                data[field] = "***REDACTED***"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using lru_cache ensures settings are parsed exactly once.
    In tests, call get_settings.cache_clear() before patching env vars.
    """
    return Settings()
