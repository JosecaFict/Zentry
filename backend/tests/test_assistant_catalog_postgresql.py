"""Opt-in check of the shopping advisor query against a migrated PostgreSQL database."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.assistant.catalog import ShoppingCatalog

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_ASSISTANT_TESTS") != "1",
    reason="Set RUN_POSTGRES_ASSISTANT_TESTS=1 to query the local migrated PostgreSQL database",
)


@pytest.mark.asyncio
async def test_catalog_query_returns_only_available_tenant_products():
    url = os.getenv("ASSISTANT_TEST_DATABASE_URL")
    if not url:
        pytest.fail("ASSISTANT_TEST_DATABASE_URL is required")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            await session.execute(text("SELECT set_config('app.rls_scope', 'global', true)"))
            tenant_id = await session.scalar(
                text("""
                SELECT p.id_tenant FROM capricho.producto p
                JOIN capricho.variante_producto v ON v.id_producto = p.id_producto
                JOIN capricho.inventario_sucursal i ON i.id_variante = v.id_variante
                    AND i.id_tenant = p.id_tenant
                WHERE p.activo AND v.activo AND i.stock_fisico > i.stock_reservado
                ORDER BY p.id_tenant LIMIT 1
            """)
            )
        if tenant_id is None:
            pytest.skip("No stocked products in the local database")
        async with sessions() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(tenant_id)}
            )
            catalog = ShoppingCatalog(session, tenant_id)
            assert await catalog.available()
            products = await catalog.for_question("Busco una polera entre 200 y 300 Bs")
            assert all(product.categoria.upper() == "POLERA" for product in products)
            assert all(200 <= product.precio <= 300 for product in products)
    finally:
        await engine.dispose()
