from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")
    app_name: str = Field(default="Zentry API", alias="APP_NAME")
    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(alias="SECRET_KEY", min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        ge=1,
        le=1440,
    )
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    cloudinary_url: str | None = Field(default=None, alias="CLOUDINARY_URL")
    brevo_api_key: str | None = Field(default=None, alias="BREVO_API_KEY")
    brevo_sender_email: str | None = Field(default=None, alias="BREVO_SENDER_EMAIL")
    brevo_sender_name: str = Field(default="Zentry", alias="BREVO_SENDER_NAME")
    password_reset_otp_expire_minutes: int = Field(
        default=10,
        alias="PASSWORD_RESET_OTP_EXPIRE_MINUTES",
        ge=5,
        le=30,
    )
    password_reset_otp_max_attempts: int = Field(
        default=5,
        alias="PASSWORD_RESET_OTP_MAX_ATTEMPTS",
        ge=3,
        le=10,
    )
    password_reset_request_cooldown_seconds: int = Field(
        default=60,
        alias="PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS",
        ge=30,
        le=600,
    )
    password_reset_token_expire_minutes: int = Field(
        default=10,
        alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
        ge=5,
        le=30,
    )
    stripe_secret_key: str | None = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str | None = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    public_web_url: str = Field(default="http://localhost:4200", alias="PUBLIC_WEB_URL")
    stripe_checkout_expire_minutes: int = Field(
        default=30,
        alias="STRIPE_CHECKOUT_EXPIRE_MINUTES",
        ge=30,
        le=1440,
    )
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_reports_model: str = Field(
        default="openai/gpt-oss-20b", alias="GROQ_REPORTS_MODEL"
    )
    groq_speech_model: str = Field(
        default="whisper-large-v3-turbo", alias="GROQ_SPEECH_MODEL"
    )
    voice_max_file_size_mb: int = Field(
        default=10, alias="VOICE_MAX_FILE_SIZE_MB", ge=1, le=25
    )
    openrouteservice_api_key: str | None = Field(
        default=None, alias="OPENROUTESERVICE_API_KEY"
    )
    ors_api_key: str | None = Field(default=None, alias="ORS_API_KEY")
    piapi_api_key: str | None = Field(default=None, alias="PIAPI_API_KEY")
    piapi_model: str = Field(default="kling", alias="PIAPI_MODEL")
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")
    hf_space: str = Field(default="yisol/IDM-VTON", alias="HF_SPACE")
    replicate_api_token: str | None = Field(default=None, alias="REPLICATE_API_TOKEN")
    replicate_model_version: str = Field(
        default="0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985",
        alias="REPLICATE_MODEL_VERSION",
    )
    tryon_provider: str = Field(default="piapi", alias="TRYON_PROVIDER")
    tryon_daily_limit_per_user: int = Field(
        default=5, alias="TRYON_DAILY_LIMIT_PER_USER", ge=1, le=50
    )
    tryon_max_file_size_mb: int = Field(
        default=5, alias="TRYON_MAX_FILE_SIZE_MB", ge=1, le=20
    )
    database_schema: Literal["capricho"] = "capricho"

    @property
    def route_service_api_key(self) -> str | None:
        return self.openrouteservice_api_key or self.ors_api_key

    @field_validator("database_url")
    @classmethod
    def validate_async_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise ValueError("CORS_ORIGINS must contain comma-separated HTTP(S) origins")
        return ",".join(origins)

    @field_validator("public_web_url")
    @classmethod
    def validate_public_web_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("PUBLIC_WEB_URL must be an HTTP(S) URL")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return self.cors_origins.split(",") if self.cors_origins else []


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
