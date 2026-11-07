"""Opt-in integration check for tenant-scoped recommendation defaults."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.recommendations.repository import RecommendationRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_RECOMMENDATION_TESTS") != "1",
    reason="Set RUN_POSTGRES_RECOMMENDATION_TESTS=1 to check the migrated PostgreSQL index",
)


@pytest.mark.asyncio
async def test_active_recommendation_index_is_scoped_to_tenant():
    url = os.getenv("RECOMMENDATION_TEST_DATABASE_URL")
    if not url:
        pytest.fail("RECOMMENDATION_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(text("SELECT set_config('app.rls_scope', 'global', true)"))
            index_sql = await session.scalar(text("""
                SELECT indexdef FROM pg_indexes
                WHERE schemaname = 'capricho'
                  AND indexname = 'uq_config_recomendador_activa'
            """))
            assert index_sql is not None and "(id_tenant)" in index_sql
            tenant_ids = (
                await session.scalars(
                    text("SELECT id_tenant FROM capricho.tenant ORDER BY id_tenant LIMIT 2")
                )
            ).all()
        if not tenant_ids:
            pytest.skip("The local database needs a tenant")
        for tenant_id in tenant_ids:
            async with sessions() as session:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :id, true)"),
                    {"id": str(tenant_id)},
                )
                config = await RecommendationRepository(session).get_active_config()
                assert config.id_tenant == tenant_id
                await session.rollback()
        async with sessions() as session:
            tenant_id = tenant_ids[0]
            await session.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"),
                {"id": str(tenant_id)},
            )
            await session.execute(text("""
                UPDATE capricho.configuracion_recomendador
                   SET activo = FALSE
                 WHERE id_tenant = :id AND activo = TRUE
            """), {"id": tenant_id})
            replacement = await RecommendationRepository(session).get_active_config()
            assert replacement.id_tenant == tenant_id
            await session.rollback()
    finally:
        await engine.dispose()
