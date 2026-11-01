"""Integration checks for PostgreSQL RLS.

These tests are intentionally opt-in because they require a migrated PostgreSQL
database and the restricted application role.  They never commit changes.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_RLS_TESTS") != "1",
    reason="Set RUN_POSTGRES_RLS_TESTS=1 and RLS_TEST_DATABASE_URL to test PostgreSQL RLS",
)


def rls_database_url() -> str:
    value = os.getenv("RLS_TEST_DATABASE_URL", "")
    if not value:
        pytest.fail("RLS_TEST_DATABASE_URL is required for PostgreSQL RLS tests")
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


@pytest.mark.asyncio
async def test_rls_is_forced_on_every_tenant_table() -> None:
    engine = create_async_engine(rls_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            role = (
                await connection.execute(
                    text(
                        """
                        SELECT r.rolsuper, r.rolbypassrls
                        FROM pg_roles r
                        WHERE r.rolname = current_user
                        """
                    )
                )
            ).one()
            assert role == (False, False), "RLS tests must use the restricted application role"

            missing = (
                await connection.execute(
                    text(
                        """
                        SELECT c.relname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        JOIN pg_attribute a ON a.attrelid = c.oid
                        WHERE n.nspname = 'capricho'
                          AND c.relkind IN ('r', 'p')
                          AND a.attname = 'id_tenant'
                          AND NOT a.attisdropped
                          AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
                        ORDER BY c.relname
                        """
                    )
                )
            ).scalars().all()
            assert missing == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tenant_cannot_read_or_update_another_tenant_user() -> None:
    engine = create_async_engine(rls_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text("SELECT set_config('app.rls_scope', 'global', true)")
                )
                tenant_ids = (
                    await connection.execute(
                        text(
                            """
                            SELECT DISTINCT id_tenant
                            FROM capricho.usuario
                            WHERE id_tenant IS NOT NULL
                            ORDER BY id_tenant
                            LIMIT 2
                            """
                        )
                    )
                ).scalars().all()
                assert len(tenant_ids) == 2, "The integration database needs two populated tenants"
                tenant_a, tenant_b = tenant_ids
                foreign_user_id = await connection.scalar(
                    text(
                        """
                        SELECT id_usuario
                        FROM capricho.usuario
                        WHERE id_tenant = :tenant_b
                        ORDER BY id_usuario
                        LIMIT 1
                        """
                    ),
                    {"tenant_b": tenant_b},
                )
                assert foreign_user_id is not None

                await transaction.rollback()
                transaction = await connection.begin()
                await connection.execute(
                    text("SELECT set_config('app.rls_scope', 'tenant', true)")
                )
                await connection.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_a)},
                )

                visible_tenants = set(
                    (
                        await connection.execute(
                            text(
                                """
                                SELECT DISTINCT id_tenant
                                FROM capricho.usuario
                                WHERE id_tenant IS NOT NULL
                                """
                            )
                        )
                    ).scalars()
                )
                assert visible_tenants <= {tenant_a}

                foreign_user = await connection.scalar(
                    text(
                        """
                        SELECT id_usuario
                        FROM capricho.usuario
                        WHERE id_usuario = :user_id
                        """
                    ),
                    {"user_id": foreign_user_id},
                )
                assert foreign_user is None

                update_result = await connection.execute(
                    text(
                        """
                        UPDATE capricho.usuario
                        SET estado = estado
                        WHERE id_usuario = :user_id
                        """
                    ),
                    {"user_id": foreign_user_id},
                )
                assert update_result.rowcount == 0
            finally:
                if transaction.is_active:
                    await transaction.rollback()
    finally:
        await engine.dispose()
