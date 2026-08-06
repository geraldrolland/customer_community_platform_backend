import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))

    EMAIL_VERIFICATION_BASE_URL: str = os.getenv(
        "EMAIL_VERIFICATION_BASE_URL", "http://localhost:3000/verify-email"
    )

    JWT_SECRET: str = os.getenv(
        "JWT_SECRET", "dev-secret-change-me-32-bytes-minimum-1234"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "7")
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )

    AUTH_TOKEN_COOKIE: str = os.getenv("AUTH_TOKEN_COOKIE", "auth_token")
    CSRF_TOKEN_COOKIE: str = os.getenv("CSRF_TOKEN_COOKIE", "csrf_token")

    COOKIE_SIGNING_SECRET: str = os.getenv("COOKIE_SIGNING_SECRET", JWT_SECRET)


settings = Settings()
