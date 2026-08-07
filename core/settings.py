"""Application settings loaded from environment variables and ``.env``.

Uses ``pydantic-settings`` so every attribute can be overridden through
environment variables; list-typed fields (``CORS_ORIGINS``,
``TRUSTED_HOSTS``) expect JSON array syntax, e.g.
``CORS_ORIGINS=["http://localhost:3000"]``.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the HappenHub API.

    Every field has a safe development default and can be overridden via
    environment variables or an ``.env`` file placed in the working
    directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "HappenHub"

    JWT_SECRET: str = "dev-secret-change-me-32-bytes-minimum-1234"
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AUTH_TOKEN_COOKIE: str = "auth_token"

    CSRF_TOKEN_COOKIE: str = "csrf_token"

    COOKIE_SIGNING_SECRET: str = "dev-secret-change-me-32-bytes-minimum-1234"

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
    ]
    TRUSTED_HOSTS: list[str] = [
        "localhost",
        "testserver",
        "127.0.0.1",
    ]


@lru_cache
def get_settings() -> Settings:
    """Build and cache the application settings singleton.

    Returns:
        Settings: The shared settings instance.
    """
    return Settings()


settings = get_settings()
