from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.tenant_context import current_tenant_id

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "search_path": f"{settings.database_schema},public",
        }
    },
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Provide one independent SQLAlchemy session per request."""
    async with async_session_factory() as session:
        tenant_id = current_tenant_id()
        if tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
        yield session


async def check_database(session: AsyncSession) -> None:
    """Execute a real, minimal database round trip."""
    result = await session.execute(text("SELECT 1"))
    if result.scalar_one() != 1:
        raise RuntimeError("Unexpected PostgreSQL readiness response")

