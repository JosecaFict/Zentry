"""Opt-in, rollback-only check of report history persistence and owner scope."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.modules.assistant.repository import AssistantRepository

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_ASSISTANT_EXPORT_TESTS') != '1', reason='Set RUN_POSTGRES_ASSISTANT_EXPORT_TESTS=1 to test report snapshot persistence')


async def test_report_snapshot_survives_history_reload_and_is_private_to_owner():
    url = os.getenv('ASSISTANT_EXPORT_TEST_DATABASE_URL')
    if not url:
        pytest.fail('ASSISTANT_EXPORT_TEST_DATABASE_URL is required')
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': 'capricho,public'}})
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text("SELECT set_config('app.rls_scope', 'global', true)"))
                user = (await connection.execute(text('SELECT id_tenant, id_usuario FROM capricho.usuario WHERE id_tenant IS NOT NULL ORDER BY id_usuario LIMIT 1'))).mappings().first()
                if not user:
                    pytest.skip('Requires a seeded user in the local database')
                await connection.execute(text("SELECT set_config('app.tenant_id', :id, true)"), {'id': str(user['id_tenant'])})
                await connection.execute(text("SELECT set_config('app.rls_scope', 'tenant', true)"))
                async with AsyncSession(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False) as session:
                    repo = AssistantRepository(session, user['id_tenant'], user['id_usuario'])
                    conversation_id = uuid4()
                    await repo.create(conversation_id, 'EMPRESA', 'GROQ', 'test')
                    snapshot = {'interpretacion': {'tipo_reporte': 'PRODUCTOS'}, 'datos': {'productos': []}, 'consultado_en': '2026-11-07T12:00:00Z'}
                    question, answer = await repo.append_exchange(conversation_id, 'Ventas de septiembre', 'Resultado', 'test', report_restricted=True, report_snapshot=snapshot)
                    assert answer.reporte_exportable
                    assert not question.reporte_exportable
                    loaded = await repo.messages(conversation_id)
                    assert loaded[-1].reporte_snapshot == snapshot
                    assert 'reporte_snapshot' not in loaded[-1].model_dump()
                    saved = await repo.report_message(conversation_id, answer.id_mensaje)
                    assert saved.reporte_snapshot == snapshot
                    assert await repo.report_message(uuid4(), answer.id_mensaje) is None
                    other_owner = AssistantRepository(session, user['id_tenant'], user['id_usuario'] + 100000)
                    assert await other_owner.report_message(conversation_id, answer.id_mensaje) is None
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
