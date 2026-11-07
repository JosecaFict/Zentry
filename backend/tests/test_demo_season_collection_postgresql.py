"""Opt-in integration check for the demo tenant catalog backfill."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_SEASON_TESTS") != "1",
    reason="Set RUN_POSTGRES_SEASON_TESTS=1 to test the local PostgreSQL migration",
)
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/20261107_0022_demo_tenant_seasons_collections.py"
)


@pytest.mark.asyncio
async def test_copy_preserves_collection_season_links_and_is_idempotent(monkeypatch):
    url = os.getenv("SEASON_TEST_DATABASE_URL")
    if not url:
        pytest.fail("SEASON_TEST_DATABASE_URL is required")
    spec = importlib.util.spec_from_file_location("demo_catalog_backfill", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    slug = f"catalog-test-{uuid4().hex[:10]}"
    monkeypatch.setattr(migration, "DEMO_SLUGS", (slug,))
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:

                def verify(sync_connection):
                    sync_connection.execute(
                        text("SELECT set_config('app.rls_scope', 'global', true)")
                    )
                    tenant_id = sync_connection.execute(
                        text(
                            "INSERT INTO capricho.tenant (nombre, slug) "
                            "VALUES ('Catalog test', :slug) RETURNING id_tenant"
                        ),
                        {"slug": slug},
                    ).scalar_one()
                    monkeypatch.setattr(migration.op, "get_bind", lambda: sync_connection)
                    source_id = sync_connection.execute(
                        text("SELECT id_tenant FROM capricho.tenant WHERE slug = 'capricho-store'")
                    ).scalar_one()
                    source_counts = sync_connection.execute(
                        text("""
                        SELECT (SELECT count(*) FROM capricho.temporada WHERE id_tenant = :id),
                               (SELECT count(*) FROM capricho.coleccion WHERE id_tenant = :id)
                    """),
                        {"id": source_id},
                    ).one()
                    migration.upgrade()
                    migration.upgrade()
                    target_counts = sync_connection.execute(
                        text("""
                        SELECT (SELECT count(*) FROM capricho.temporada WHERE id_tenant = :id),
                               (SELECT count(*) FROM capricho.coleccion WHERE id_tenant = :id)
                    """),
                        {"id": tenant_id},
                    ).one()
                    assert target_counts == source_counts
                    linked_counts = sync_connection.execute(
                        text("""
                        SELECT (SELECT count(*) FROM capricho.coleccion
                                WHERE id_tenant = :source AND id_temporada IS NOT NULL),
                               (SELECT count(*) FROM capricho.coleccion
                                WHERE id_tenant = :target AND id_temporada IS NOT NULL)
                    """),
                        {"source": source_id, "target": tenant_id},
                    ).one()
                    assert linked_counts[0] == linked_counts[1]
                    cross_tenant_links = sync_connection.execute(
                        text("""
                        SELECT count(*) FROM capricho.coleccion c
                        JOIN capricho.temporada s ON s.id_temporada = c.id_temporada
                        WHERE c.id_tenant = :id AND s.id_tenant <> :id
                    """),
                        {"id": tenant_id},
                    ).scalar_one()
                    assert cross_tenant_links == 0

                await connection.run_sync(verify)
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
