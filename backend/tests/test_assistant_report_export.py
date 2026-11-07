from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from zipfile import ZipFile
from xml.etree import ElementTree

from app.modules.assistant.schemas import Conversation, Message
from app.modules.assistant.service import AssistantService
from app.modules.reports.service import ReportsService


def setup_export(monkeypatch):
    principal = SimpleNamespace(
        id_tenant=7, user=SimpleNamespace(id_usuario=91), tenant_slug='capricho-store',
        session_id=str(uuid4()), roles=frozenset({'ADMIN'}), plan_codigo='PROFESIONAL',
        permite_reportes_ia=True, permissions=frozenset({'ventas.ver', 'inventario.ver'}),
    )
    service = AssistantService(AsyncMock(), principal)
    conversation = Conversation(
        id_conversacion=uuid4(), modo='EMPRESA', proveedor='GROQ', modelo='test', estado='ACTIVA',
        created_at='2026-11-07T12:00:00Z', updated_at='2026-11-07T12:00:00Z',
    )
    service.repo.get = AsyncMock(return_value=conversation)
    message = Message(
        id_mensaje=12, rol='ASISTENTE', contenido='Reporte de septiembre', created_at='2026-11-07T12:00:00Z',
        requiere_reportes_ia=True, reporte_snapshot={
            'interpretacion': {'tipo_reporte': 'PRODUCTOS', 'fecha_desde': '2026-09-01', 'fecha_hasta': '2026-09-30', 'limite': 1},
            'consultado_en': '2026-11-07T12:00:00Z',
            'datos': {'desde': '2026-09-01', 'hasta': '2026-09-30', 'productos': [
                {'posicion': 1, 'id_producto': 5, 'producto': 'Polo clásico', 'categoria': 'POLO', 'unidades': 21, 'ingresos': '4200.00'},
            ]},
        },
    )
    service.repo.report_message = AsyncMock(return_value=message)
    audit = AsyncMock()
    monkeypatch.setattr(ReportsService, 'audit_access', audit)
    # Exporting must never rerun the interpreter or query current business figures.
    query = AsyncMock(side_effect=AssertionError('No volver a consultar el reporte'))
    monkeypatch.setattr('app.modules.reports.router._execute_ai_plan', query)
    return service, conversation, message, audit, query


@pytest.mark.parametrize('file_format', ['pdf', 'xlsx'])
async def test_export_uses_the_saved_report_and_audits_download(monkeypatch, file_format):
    service, conversation, message, audit, query = setup_export(monkeypatch)
    content, media, filename = await service.export_report(conversation.id_conversacion, 12, file_format)
    assert filename == f'reporte-chat-12.{file_format}'
    assert content.startswith(b'%PDF' if file_format == 'pdf' else b'PK')
    if file_format == 'xlsx':
        with ZipFile(BytesIO(content)) as workbook:
            root = ElementTree.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
        values = [node.text for node in root.iter() if node.tag.rsplit('}', 1)[-1] in {'t', 'v'}]
        assert 'Polo clásico' in values
        assert '21' in values
        assert any(value and value.startswith('4200') for value in values)
    audit.assert_awaited_once()
    assert audit.await_args.kwargs['metadata']['fecha_desde'].isoformat() == '2026-09-01'
    assert audit.await_args.kwargs['metadata']['fecha_consulta'] == '2026-11-07T12:00:00Z'
    service.repo.report_message.assert_awaited_once_with(conversation.id_conversacion, 12)
    query.assert_not_awaited()


@pytest.mark.parametrize('missing', ['plan', 'permission'])
async def test_export_checks_current_plan_and_permissions(monkeypatch, missing):
    service, conversation, _, audit, _ = setup_export(monkeypatch)
    if missing == 'plan':
        service.principal.plan_codigo = 'BASICO'
    else:
        service.principal.permissions = frozenset({'ventas.ver'})
    with pytest.raises(HTTPException) as caught:
        await service.export_report(conversation.id_conversacion, 12, 'pdf')
    assert caught.value.status_code == 403
    service.repo.report_message.assert_not_awaited()
    audit.assert_not_awaited()


async def test_message_from_another_conversation_is_not_exported(monkeypatch):
    service, conversation, _, audit, _ = setup_export(monkeypatch)
    service.repo.report_message.return_value = None
    with pytest.raises(HTTPException) as caught:
        await service.export_report(conversation.id_conversacion, 99, 'pdf')
    assert caught.value.status_code == 404
    audit.assert_not_awaited()


async def test_legacy_message_requires_a_new_query_and_cannot_export(monkeypatch):
    service, conversation, message, _, _ = setup_export(monkeypatch)
    message.reporte_snapshot = None
    with pytest.raises(HTTPException) as caught:
        await service.export_report(conversation.id_conversacion, 12, 'xlsx')
    assert caught.value.status_code == 409


def test_public_message_hides_raw_report_and_downgrade_hides_export(monkeypatch):
    service, _, message, _, _ = setup_export(monkeypatch)
    assert message.model_dump()['reporte_exportable'] is True
    assert 'reporte_snapshot' not in message.model_dump()
    service._mask_report_messages([message])
    assert message.model_dump()['reporte_exportable'] is False
    assert 'plan Profesional' in message.contenido
