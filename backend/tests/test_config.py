import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(database_url: str, cors_origins: str = "") -> Settings:
    return Settings(
        DATABASE_URL=database_url,
        SECRET_KEY="test-secret-key-not-for-production",
        CORS_ORIGINS=cors_origins,
    )


@pytest.mark.parametrize("scheme", ["postgres://", "postgresql://"])
def test_railway_database_url_uses_asyncpg(scheme: str) -> None:
    settings = make_settings(f"{scheme}user:password@postgres.railway.internal:5432/railway")
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_asyncpg_database_url_is_preserved() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5433/Capricho-Store"
    assert make_settings(url).database_url == url


def test_runtime_database_url_prefers_restricted_application_role() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://postgres:admin@postgres.internal/railway",
        APP_DATABASE_URL="postgresql://zentry_app:restricted@postgres.internal/railway",
        SECRET_KEY="test-secret-key-not-for-production",
    )

    assert settings.database_url.startswith("postgresql+asyncpg://postgres:")
    assert settings.runtime_database_url.startswith(
        "postgresql+asyncpg://zentry_app:"
    )


def test_runtime_database_url_falls_back_to_migration_url() -> None:
    settings = make_settings("postgresql://postgres:admin@localhost/railway")

    assert settings.runtime_database_url == settings.database_url


def test_cors_origins_are_cleaned() -> None:
    settings = make_settings(
        "postgresql://user:password@localhost/database",
        " https://web.example.com/, http://localhost:4200 ",
    )
    assert settings.cors_origin_list == [
        "https://web.example.com",
        "http://localhost:4200",
    ]


def test_invalid_cors_origin_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(
            "postgresql://user:password@localhost/database",
            "web.example.com",
        )


def test_stripe_checkout_configuration_is_normalized() -> None:
    settings = Settings(
        DATABASE_URL="postgresql://user:password@localhost/database",
        SECRET_KEY="test-secret-key-not-for-production",
        PUBLIC_WEB_URL="https://capricho-store.vercel.app/",
        STRIPE_CHECKOUT_EXPIRE_MINUTES=45,
    )
    assert settings.public_web_url == "https://capricho-store.vercel.app"
    assert settings.stripe_checkout_expire_minutes == 45


def test_stripe_checkout_cannot_hold_stock_less_than_thirty_minutes() -> None:
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL="postgresql://user:password@localhost/database",
            SECRET_KEY="test-secret-key-not-for-production",
            STRIPE_CHECKOUT_EXPIRE_MINUTES=10,
        )
