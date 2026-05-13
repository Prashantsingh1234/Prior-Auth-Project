"""Unit tests for configuration settings validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config.settings import Settings


class TestSettingsValidation:

    def test_valid_settings_loads(self) -> None:
        """Settings with all required fields loads without error."""
        s = Settings(secret_key="a" * 32, environment="development")
        assert s.environment == "development"

    def test_invalid_environment_raises(self) -> None:
        """Invalid environment value raises ValidationError."""
        with pytest.raises(ValidationError, match="environment"):
            Settings(secret_key="a" * 32, environment="invalid_env")

    def test_production_debug_raises(self) -> None:
        """debug=True in production raises ValidationError."""
        with pytest.raises(ValidationError, match="DEBUG must be False"):
            Settings(secret_key="a" * 32, environment="production", debug=True)

    def test_database_url_built_correctly(self) -> None:
        """database_url property builds correct async MySQL DSN."""
        s = Settings(
            secret_key="a" * 32,
            db_host="mysql-host",
            db_port=3306,
            db_name="mydb",
            db_user="user",
            db_password="pass",  # type: ignore[arg-type]
        )
        assert "mysql+aiomysql://" in s.database_url
        assert "mysql-host:3306/mydb" in s.database_url

    def test_safe_dict_redacts_secrets(self) -> None:
        """safe_dict() must not expose secret field values."""
        s = Settings(secret_key="my-super-secret-key-12345678901234")
        safe = s.safe_dict()
        assert safe.get("secret_key") == "***REDACTED***"

    def test_is_production_flag(self) -> None:
        s = Settings(secret_key="a" * 32, environment="production", debug=False)
        assert s.is_production is True
        assert s.is_development is False

    def test_docs_disabled_in_production(self) -> None:
        s = Settings(secret_key="a" * 32, environment="production", debug=False)
        assert s.docs_enabled is False

    def test_docs_enabled_in_development(self) -> None:
        s = Settings(secret_key="a" * 32, environment="development", debug=True)
        assert s.docs_enabled is True
