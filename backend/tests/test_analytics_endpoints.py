from datetime import date
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.analytics.dependencies import get_analytics_service
from app.modules.analytics.schemas import (
    AnalyticsDashboard,
    CustomerSegmentation,
    DemandForecast,
)
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario


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
        session_id="analytics-test-session",
        id_sucursal=branch_id,
        sucursal=branch_name,
        id_tenant=tenant_id,
        tenant_slug="tenant-demo",
        plan_codigo="PROFESIONAL" if ai_enabled else "BASICO",
        permite_reportes_ia=ai_enabled,
    )


SAMPLE = AnalyticsDashboard(
    generado_en=date(2026, 10, 29),
    periodo_desde=date(2026, 7, 31),
    periodo_hasta=date(2026, 10, 29),
    sucursal="Todas las sucursales",
    periodo="TRIMESTRAL",
    prediccion_demanda=DemandForecast(
        modelo="Regresión lineal temporal",
        objetivo="Unidades vendidas por semana",
        granularidad="SEMANA",
        observaciones_entrenamiento=13,
        fecha_entrenamiento=date(2026, 10, 29),
        mae_unidades=2.5,
        r2_unidades=0.6,
        tendencia_por_periodo=1.2,
        confianza="MEDIA",
        advertencia=None,
        pronostico=[],
    ),
    segmentacion_clientes=CustomerSegmentation(
        modelo="K-means RFM",
        variables=["recencia", "frecuencia", "valor monetario"],
        clientes_analizados=0,
        segmentos=[],
    ),
)


async def request_dashboard(actor: CurrentPrincipal, service: AsyncMock, query: str = ""):
    app.dependency_overrides[get_current_principal] = lambda: actor
    app.dependency_overrides[get_analytics_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(f"/api/v1/admin/analytics/dashboard{query}")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analytics_requires_professional_plan() -> None:
    service = AsyncMock()
    response = await request_dashboard(principal(ai_enabled=False), service)

    assert response.status_code == 403
    service.dashboard.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_query_keeps_tenant_scope_and_accepts_authorized_branch() -> None:
    service = AsyncMock()
    service.dashboard.return_value = SAMPLE
    actor = principal(permissions=("ventas.ver", "inventario.ver", "ventas.sucursales_todas"))

    response = await request_dashboard(actor, service, "?id_sucursal=12&periodo=TRIMESTRAL")

    assert response.status_code == 200
    service.dashboard.assert_awaited_once_with(
        tenant_id=7,
        branch_id=12,
        branch_name=None,
        periodo="TRIMESTRAL",
    )


@pytest.mark.asyncio
async def test_branch_employee_cannot_escape_assigned_branch() -> None:
    service = AsyncMock()
    service.dashboard.return_value = SAMPLE
    actor = principal(
        roles=("EMPLEADO",),
        branch_id=4,
        branch_name="Sucursal Norte",
    )

    response = await request_dashboard(actor, service, "?id_sucursal=99&periodo=MENSUAL")

    assert response.status_code == 200
    service.dashboard.assert_awaited_once_with(
        tenant_id=7,
        branch_id=4,
        branch_name="Sucursal Norte",
        periodo="MENSUAL",
    )


@pytest.mark.asyncio
async def test_analytics_rejects_unknown_period() -> None:
    service = AsyncMock()
    response = await request_dashboard(principal(), service, "?periodo=ANUAL")

    assert response.status_code == 422
    service.dashboard.assert_not_awaited()
