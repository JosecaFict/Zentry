from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.platform.dependencies import (
    get_platform_service,
    require_platform_database_scope,
)
from app.modules.platform.models import Plan, Subscription, Tenant
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.router import search_public_tenants
from app.modules.platform.schemas import PlatformOverview, TenantPublicResponse, TenantUpdate
from app.modules.platform.service import PlatformService


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
@pytest.mark.parametrize("branches", [10, 12])
async def test_enterprise_downgrade_checks_branch_limit(branches: int) -> None:
    session = AsyncMock()
    tenant = Tenant(nombre="Línea Urbana")
    current = Plan(
        id_plan=3, nombre="Empresarial", max_sucursales_activas=25,
        max_usuarios_internos=100, max_productos_activos=50000,
    )
    target = Plan(
        id_plan=2, nombre="Profesional", max_sucursales_activas=10,
        max_usuarios_internos=25, max_productos_activos=20000, precio_mensual=700,
    )
    subscription = Subscription(id_plan=3, precio_acordado=1500)
    session.get.return_value = tenant
    repository = PlatformRepository(session)
    repository.get_active_plan = AsyncMock(return_value=target)
    repository.get_subscription = AsyncMock(return_value=(subscription, current))
    repository.tenant_nit_exists = AsyncMock(return_value=False)
    session.scalar.side_effect = [branches, 25, 20000]
    payload = TenantUpdate(nombre="Línea Urbana actualizada", id_plan=2)

    if branches == 10:
        assert await repository.update_tenant(1, payload)
        assert subscription.id_plan == 2
        assert subscription.precio_acordado == 700
        session.flush.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as error:
            await PlatformService(repository).update_tenant(1, payload)
        assert error.value.status_code == 409
        assert "12 sucursales activas (máximo 10)" in error.value.detail
        assert subscription.id_plan == 3
        assert tenant.nombre == "Línea Urbana"
        session.flush.assert_not_awaited()
        session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_platform_overview_accepts_superadmin() -> None:
    service = AsyncMock()
    service.overview.return_value = PlatformOverview(
        tenants_total=1,
        tenants_activos=1,
        tenants_suspendidos=0,
        sucursales_activas=2,
        suscripciones_por_vencer=0,
        suscripciones_en_gracia=0,
        suscripciones_suspendidas=0,
    )
    app.dependency_overrides[get_current_principal] = lambda: principal(global_user=True)
    app.dependency_overrides[get_platform_service] = lambda: service
    app.dependency_overrides[require_platform_database_scope] = lambda: None
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
async def test_public_tenant_search_requires_no_session() -> None:
    service = AsyncMock()
    service.search_public_tenants.return_value = [
        TenantPublicResponse(
            nombre="Capricho Store",
            slug="capricho-store",
            logo_url=None,
            color_primario="#064FE8",
            color_primario_oscuro="#0039B8",
        )
    ]
    response = await search_public_tenants(service=service, query="capricho")

    assert response[0].slug == "capricho-store"
    service.search_public_tenants.assert_awaited_once_with("capricho")


@pytest.mark.asyncio
async def test_public_tenant_search_allows_initial_catalog() -> None:
    service = AsyncMock()
    service.search_public_tenants.return_value = []

    response = await search_public_tenants(service=service, query="")

    assert response == []
    service.search_public_tenants.assert_awaited_once_with("")


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
    app.dependency_overrides[require_platform_database_scope] = lambda: None
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
