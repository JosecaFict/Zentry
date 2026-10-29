from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.reports.ai import AIReportInterpreterError
from app.modules.reports.dependencies import (
    get_ai_report_interpreter,
    get_reports_service,
    get_speech_transcriber,
)
from app.modules.reports.schemas import AIReportPlan, InventoryReport


def principal(
    *,
    tenant_id: int = 7,
    roles: tuple[str, ...] = ("ADMIN",),
    permissions: tuple[str, ...] = ("ventas.ver", "inventario.ver"),
    branch_id: int | None = None,
    branch_name: str | None = None,
    ai_enabled: bool = True,
) -> CurrentPrincipal:
    user = Usuario(
        id_usuario=41,
        id_tenant=tenant_id,
        nombres="Ana",
        apellidos="Analista",
        correo="ana@example.com",
        password_hash="unused",
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        session_id="reports-security-session",
        id_sucursal=branch_id,
        sucursal=branch_name,
        id_tenant=tenant_id,
        tenant_slug="tenant-demo",
        plan_codigo="PROFESIONAL" if ai_enabled else "BASICO",
        permite_reportes_ia=ai_enabled,
    )


async def post(
    path: str,
    actor: CurrentPrincipal,
    service: AsyncMock,
    interpreter: AsyncMock,
    payload: dict,
):
    app.dependency_overrides[get_current_principal] = lambda: actor
    app.dependency_overrides[get_reports_service] = lambda: service
    app.dependency_overrides[get_ai_report_interpreter] = lambda: interpreter
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(path, json=payload)
    finally:
        app.dependency_overrides.clear()


async def post_audio(actor: CurrentPrincipal, service: AsyncMock, transcriber: AsyncMock):
    app.dependency_overrides[get_current_principal] = lambda: actor
    app.dependency_overrides[get_reports_service] = lambda: service
    app.dependency_overrides[get_speech_transcriber] = lambda: transcriber
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(
                "/api/v1/admin/reports/ai/transcribe",
                files={"audio": ("consulta.webm", b"audio-demo", "audio/webm")},
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_reports_require_professional_plan() -> None:
    service = AsyncMock()
    interpreter = AsyncMock()

    response = await post(
        "/api/v1/admin/reports/ai/query",
        principal(ai_enabled=False),
        service,
        interpreter,
        {"pregunta": "Muéstrame las ventas"},
    )

    assert response.status_code == 403
    interpreter.interpret.assert_not_awaited()
    service.audit_access.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_failure_does_not_expose_internal_details() -> None:
    service = AsyncMock()
    interpreter = AsyncMock()
    interpreter.interpret.side_effect = AIReportInterpreterError(
        "token sk-secret-provider y respuesta interna"
    )

    response = await post(
        "/api/v1/admin/reports/ai/query",
        principal(),
        service,
        interpreter,
        {"pregunta": "Muéstrame las ventas"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "El asistente no pudo procesar la consulta en este momento"
    )
    assert "sk-secret-provider" not in response.text
    service.audit_access.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_query_audits_sanitized_metadata_without_question() -> None:
    service = AsyncMock()
    service.inventory.return_value = InventoryReport(
        unidades_disponibles=0,
        valor_total="0.00",
        items_criticos=0,
        items=[],
    )
    interpreter = AsyncMock()
    interpreter.interpret.return_value = AIReportPlan(
        tipo_reporte="INVENTARIO",
        solo_criticos=True,
        visualizacion="INDICADORES",
    )

    response = await post(
        "/api/v1/admin/reports/ai/query",
        principal(),
        service,
        interpreter,
        {"pregunta": "Pregunta comercial confidencial"},
    )

    assert response.status_code == 200
    audit_call = service.audit_access.await_args.kwargs
    assert audit_call["tenant_id"] == 7
    assert audit_call["user_id"] == 41
    assert audit_call["action"] == "CONSULTAR"
    assert audit_call["entity"] == "REPORTE_IA"
    assert "pregunta" not in audit_call["metadata"]
    assert "Pregunta comercial confidencial" not in str(audit_call)


@pytest.mark.asyncio
async def test_branch_employee_cannot_export_another_branch() -> None:
    service = AsyncMock()
    service.inventory.return_value = InventoryReport(
        unidades_disponibles=0,
        valor_total="0.00",
        items_criticos=0,
        items=[],
    )
    interpreter = AsyncMock()
    actor = principal(
        roles=("EMPLEADO",),
        branch_id=4,
        branch_name="Sucursal Norte",
    )
    payload = {
        "id_sucursal": 99,
        "interpretacion": {
            "tipo_reporte": "INVENTARIO",
            "solo_criticos": True,
            "visualizacion": "TABLA",
        },
    }

    response = await post(
        "/api/v1/admin/reports/ai/export/xlsx",
        actor,
        service,
        interpreter,
        payload,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    service.inventory.assert_awaited_once_with(7, 4, True, None, None)
    audit_call = service.audit_access.await_args.kwargs
    assert audit_call["metadata"]["id_sucursal"] == 4
    assert audit_call["metadata"]["formato"] == "xlsx"


@pytest.mark.asyncio
async def test_voice_transcription_requires_professional_plan() -> None:
    service = AsyncMock()
    transcriber = AsyncMock()
    transcriber.model = "whisper-large-v3-turbo"

    response = await post_audio(principal(ai_enabled=False), service, transcriber)

    assert response.status_code == 403
    transcriber.transcribe.assert_not_awaited()


@pytest.mark.asyncio
async def test_voice_transcription_returns_text_and_audits_without_audio() -> None:
    service = AsyncMock()
    transcriber = AsyncMock()
    transcriber.model = "whisper-large-v3-turbo"
    transcriber.transcribe.return_value = "Muéstrame las ventas de este mes"

    response = await post_audio(principal(), service, transcriber)

    assert response.status_code == 200
    assert response.json() == {"texto": "Muéstrame las ventas de este mes"}
    transcriber.transcribe.assert_awaited_once_with(
        "consulta.webm", "audio/webm", b"audio-demo"
    )
    audit_call = service.audit_access.await_args.kwargs
    assert audit_call["action"] == "TRANSCRIBIR"
    assert audit_call["record_id"] == "VOZ"
    assert "audio-demo" not in str(audit_call)
    assert "Muéstrame" not in str(audit_call)
