from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.platform.dependencies import get_platform_service
from app.modules.platform.schemas import PlatformOverview


def principal(*, global_user: bool) -> CurrentPrincipal:
    user = Usuario(
        id_usuario=90 if global_user else 1,
        id_tenant=None if global_user else 1,
        nombres="Platform",
        apellidos="Operator",
        correo="platform@example.com",
        password_hash="unused",
        estado="ACTIVO",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset({"SUPERADMIN"} if global_user else {"ADMIN"}),
        permissions=frozenset(
            {
                "platform.overview.ver",
                "platform.tenants.ver",
                "platform.tenants.gestionar",
            }
            if global_user
            else {"empleados.ver"}
        ),
        session_id="test-session",
        id_tenant=user.id_tenant,
    )


@pytest.mark.asyncio
async def test_platform_overview_accepts_superadmin() -> None:
    service = AsyncMock()
    service.overview.return_value = PlatformOverview(
        tenants_total=1,
        tenants_activos=1,
        tenants_suspendidos=0,
        sucursales_activas=2,
        suscripciones_por_vencer=0,
    )
    app.dependency_overrides[get_current_principal] = lambda: principal(global_user=True)
    app.dependency_overrides[get_platform_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/platform/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["tenants_total"] == 1


@pytest.mark.asyncio
async def test_platform_overview_rejects_tenant_admin() -> None:
    app.dependency_overrides[get_current_principal] = lambda: principal(global_user=False)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/platform/overview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_platform_can_create_tenant() -> None:
    service = AsyncMock()
    service.create_tenant.return_value = {
        "id_tenant": 7,
        "nombre": "Nueva Empresa",
        "slug": "nueva-empresa",
        "logo_url": None,
        "estado": "ACTIVO",
        "plan_codigo": "BASICO",
        "plan_nombre": "Básico",
        "subscription_estado": "ACTIVA",
        "fecha_fin": None,
        "sucursales_activas": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "usuarios": 1,
        "administradores": 1,
    }
    app.dependency_overrides[get_current_principal] = lambda: principal(global_user=True)
    app.dependency_overrides[get_platform_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/platform/tenants",
                json={
                    "nombre": "Nueva Empresa",
                    "slug": "nueva-empresa",
                    "id_plan": 1,
                    "administrador": {
                        "nombres": "Ana",
                        "apellidos": "Admin",
                        "correo": "ana@example.com",
                        "password": "Temporal1!",
                    },
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["slug"] == "nueva-empresa"
    service.create_tenant.assert_awaited_once()
